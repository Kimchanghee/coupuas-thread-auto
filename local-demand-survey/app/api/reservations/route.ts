import { google, type sheets_v4 } from "googleapis";
import { ExternalAccountClient } from "google-auth-library";
import type { SurveyResponse } from "../../lib/survey.ts";
import { handleSurveyDelete, handleSurveyHealth, handleSurveyMirrorRetry, handleSurveyPost, isSecureSurveySecret, type SurveyHealthDependencies, type SurveyMirror, type SurveyServiceDependencies } from "./service.ts";
import { resolveRedisRestConfig, UpstashRedis, UpstashSurveyRateLimiter, UpstashSurveyStore } from "./store.ts";
import { toSheetRow } from "./sheet-row.ts";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DEFAULT_SHEET_NAME = "응답 원본";

function requiredEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is not configured`);
  return value;
}

function requiredSecretEnv(name: string, distinctFrom: string): string {
  const value = requiredEnv(name);
  const other = process.env[distinctFrom]?.trim() ?? "";
  if (!isSecureSurveySecret(value, other)) throw new Error(`${name} is insecure or duplicates ${distinctFrom}`);
  return value;
}

function positiveIntegerEnv(name: string, fallback: number): number {
  const value = Number(process.env[name]);
  return Number.isInteger(value) && value > 0 ? value : fallback;
}

function sheetName(): string {
  return process.env.GOOGLE_SHEETS_SHEET_NAME?.trim() || DEFAULT_SHEET_NAME;
}

function quoteSheetName(value: string): string {
  return `'${value.replaceAll("'", "''")}'`;
}

function sheetsClient(request: Request): sheets_v4.Sheets {
  const oidcToken = request.headers.get("x-vercel-oidc-token");
  if (!oidcToken) {
    if (process.env.NODE_ENV === "production") throw new Error("Vercel OIDC token is missing");
    const auth = new google.auth.GoogleAuth({ scopes: ["https://www.googleapis.com/auth/spreadsheets"] });
    return google.sheets({ version: "v4", auth });
  }

  const projectNumber = requiredEnv("GCP_PROJECT_NUMBER");
  const serviceAccountEmail = requiredEnv("GCP_SERVICE_ACCOUNT_EMAIL");
  const poolId = requiredEnv("GCP_WORKLOAD_IDENTITY_POOL_ID");
  const providerId = requiredEnv("GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID");
  const audience = `//iam.googleapis.com/projects/${projectNumber}/locations/global/workloadIdentityPools/${poolId}/providers/${providerId}`;
  const auth = ExternalAccountClient.fromJSON({
    type: "external_account",
    audience,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
    subject_token_type: "urn:ietf:params:oauth:token-type:jwt",
    token_url: "https://sts.googleapis.com/v1/token",
    service_account_impersonation_url: `https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${serviceAccountEmail}:generateAccessToken`,
    subject_token_supplier: { getSubjectToken: async () => oidcToken },
  });
  if (!auth) throw new Error("Google Workload Identity client initialization failed");
  return google.sheets({ version: "v4", auth });
}

class GoogleSheetsMirror implements SurveyMirror {
  private readonly spreadsheetId = process.env.GOOGLE_SHEETS_SPREADSHEET_ID?.trim() || "";
  private readonly rangePrefix = quoteSheetName(sheetName());

  constructor(private readonly request: Request) {}

  private client(): sheets_v4.Sheets {
    if (!this.spreadsheetId) throw new Error("GOOGLE_SHEETS_SPREADSHEET_ID is not configured");
    return sheetsClient(this.request);
  }

  private async rowNumber(responseId: string): Promise<number | null> {
    const existing = await this.client().spreadsheets.values.get({
      spreadsheetId: this.spreadsheetId,
      range: `${this.rangePrefix}!A2:A`,
      majorDimension: "COLUMNS",
    });
    const index = (existing.data.values?.[0] ?? []).findIndex((value) => String(value) === responseId);
    return index < 0 ? null : index + 2;
  }

  async append(response: SurveyResponse): Promise<void> {
    if (await this.rowNumber(response.id) !== null) return;
    await this.client().spreadsheets.values.append({
      spreadsheetId: this.spreadsheetId,
      range: `${this.rangePrefix}!A:AJ`,
      valueInputOption: "RAW",
      insertDataOption: "INSERT_ROWS",
      includeValuesInResponse: false,
      requestBody: { values: [toSheetRow(response)] },
    });
  }

  async remove(responseId: string): Promise<void> {
    if (!this.spreadsheetId) return;
    const row = await this.rowNumber(responseId);
    if (row === null) return;
    await this.client().spreadsheets.values.clear({
      spreadsheetId: this.spreadsheetId,
      range: `${this.rangePrefix}!A${row}:AJ${row}`,
    });
  }

  async health(): Promise<boolean> {
    if (!this.spreadsheetId) return false;
    const response = await this.client().spreadsheets.values.get({
      spreadsheetId: this.spreadsheetId,
      range: `${this.rangePrefix}!A1:A2`,
    });
    return Boolean(response.data.values?.length);
  }
}

function dependencies(request: Request): SurveyServiceDependencies {
  const redisConfig = resolveRedisRestConfig();
  const redis = new UpstashRedis(redisConfig.url, redisConfig.token);
  return {
    store: new UpstashSurveyStore(redis),
    rateLimiter: new UpstashSurveyRateLimiter(
      redis,
      positiveIntegerEnv("SURVEY_RATE_LIMIT_IP_PER_HOUR", 10),
      positiveIntegerEnv("SURVEY_RATE_LIMIT_EMAIL_PER_DAY", 3),
    ),
    mirror: new GoogleSheetsMirror(request),
    hmacSecret: requiredSecretEnv("SURVEY_SECURITY_HMAC_SECRET", "SURVEY_HEALTH_CHECK_SECRET"),
    logger: console,
  };
}

function healthDependencies(request: Request): SurveyHealthDependencies {
  const redisConfig = resolveRedisRestConfig();
  const redis = new UpstashRedis(redisConfig.url, redisConfig.token);
  return {
    store: new UpstashSurveyStore(redis),
    mirror: new GoogleSheetsMirror(request),
    healthSecret: requiredSecretEnv("SURVEY_HEALTH_CHECK_SECRET", "SURVEY_SECURITY_HMAC_SECRET"),
    logger: console,
  };
}

export async function GET(request: Request) {
  try {
    return await handleSurveyHealth(request, healthDependencies(request));
  } catch (error) {
    console.error("Survey health check failed", error instanceof Error ? error.message : "unknown error");
    return Response.json({ ok: false, authoritative: "unconfigured", mirror: "unknown" }, { status: 503 });
  }
}

export async function POST(request: Request) {
  try {
    return await handleSurveyPost(request, dependencies(request));
  } catch (error) {
    console.error("Survey service configuration failed", error instanceof Error ? error.message : "unknown error");
    return Response.json({ ok: false, message: "설문 저장소 설정이 완료되지 않았습니다." }, { status: 503 });
  }
}

export async function PATCH(request: Request) {
  try {
    return await handleSurveyMirrorRetry(request, dependencies(request));
  } catch (error) {
    console.error("Survey service configuration failed", error instanceof Error ? error.message : "unknown error");
    return Response.json({ ok: false, message: "설문 저장소 설정이 완료되지 않았습니다." }, { status: 503 });
  }
}

export async function DELETE(request: Request) {
  try {
    return await handleSurveyDelete(request, dependencies(request));
  } catch (error) {
    console.error("Survey service configuration failed", error instanceof Error ? error.message : "unknown error");
    return Response.json({ ok: false, message: "설문 저장소 설정이 완료되지 않았습니다." }, { status: 503 });
  }
}
