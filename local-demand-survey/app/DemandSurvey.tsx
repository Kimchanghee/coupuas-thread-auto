"use client";

import { useEffect, useState } from "react";
import {
  bottlenecks,
  bundleItems,
  comfortablePriceOptions,
  contactMethodOptions,
  controlPreferenceOptions,
  courseTopics,
  desiredPostOptions,
  formFromSubmission,
  initialForm,
  isSurveyResponse,
  liveTimeOptions,
  monthlyPostOptions,
  paymentPreferenceOptions,
  platforms,
  priceReactionOptions,
  purchaseBlockers,
  purchaseTimingOptions,
  stages,
  supportOptions,
  toolOptions,
  validateSurveySubmission,
  type FormState,
  type SurveyResponse,
} from "./lib/survey.ts";
import {
  clearDraftStorage,
  clearLegacySurveyStorage,
  clearSurveyStorage,
  createSubmissionCredential,
  loadDraft,
  loadReceipt,
  isReceiptExpired,
  receiptSummary,
  saveDraft,
  saveReceipt,
  type ReceiptMirrorStatus,
  type ReceiptSummary,
  type SubmissionCredential,
} from "./lib/client-storage.ts";

const steps = [
  { eyebrow: "현재 상태", title: "지금 어디까지 해보셨나요?", note: "응답자의 경험 수준과 관심 플랫폼을 구분합니다." },
  { eyebrow: "실제 병목", title: "어디에서 시간이 가장 많이 새나요?", note: "자동화가 해결해야 할 우선순위를 찾습니다." },
  { eyebrow: "구매 조건", title: "70만원 패키지를 어떻게 판단하시나요?", note: "가격만이 아니라 구매를 막는 진짜 이유를 확인합니다." },
  { eyebrow: "강의 설계", title: "개인 강의에서 무엇을 먼저 해결해야 할까요?", note: "강의 순서와 원격지원 범위를 결정합니다." },
  { eyebrow: "마지막 질문", title: "고객님의 표현을 그대로 듣고 싶습니다", note: "마케팅 문구와 후속 인터뷰에 활용합니다." },
];

function toggle(list: string[], value: string, max?: number) {
  if (list.includes(value)) return list.filter((item) => item !== value);
  if (max && list.length >= max) return list;
  return [...list, value];
}

function ChoiceGrid({ label, options, value, onChange }: { label: string; options: readonly string[]; value: string; onChange: (value: string) => void }) {
  return (
    <div className="choice-grid" role="radiogroup" aria-label={label}>
      {options.filter(Boolean).map((option) => (
        <label
          key={option}
          className={`choice ${value === option ? "selected" : ""}`}
        >
          <input className="choice-native" type="radio" name={label} value={option} checked={value === option} onChange={() => onChange(option)} />
          <span className="choice-dot" aria-hidden="true" />
          {option}
        </label>
      ))}
    </div>
  );
}

function MultiChoice({ label, options, values, onChange, max }: { label: string; options: readonly string[]; values: string[]; onChange: (values: string[]) => void; max?: number }) {
  return (
    <div className="choice-grid" role="group" aria-label={label}>
      {options.map((option) => {
        const selected = values.includes(option);
        const disabled = Boolean(max && !selected && values.length >= max);
        return (
          <button
            key={option}
            type="button"
            disabled={disabled}
            aria-pressed={selected}
            className={`choice multi ${selected ? "selected" : ""}`}
            onClick={() => onChange(toggle(values, option, max))}
          >
            <span className="check-box" aria-hidden="true">{selected ? "✓" : ""}</span>
            {option}
          </button>
        );
      })}
    </div>
  );
}

function Question({ number, title, description, children }: { number: string; title: string; description?: string; children: React.ReactNode }) {
  const headingId = `question-${number}`;
  return (
    <section className="question-block" aria-labelledby={headingId}>
      <div className="question-heading">
        <span aria-hidden="true">{number}</span>
        <div>
          <h3 id={headingId}>{title}</h3>
          {description && <p>{description}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

type SubmissionApiResponse = {
  ok?: boolean;
  message?: string;
  mirrorStatus?: "pending" | "mirrored";
  response?: unknown;
};

export function DemandSurvey() {
  const [view, setView] = useState<"survey" | "thanks">("survey");
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormState>(initialForm);
  const [credential, setCredential] = useState<SubmissionCredential | null>(null);
  const [lastResponse, setLastResponse] = useState<SurveyResponse | ReceiptSummary | null>(null);
  const [mirrorStatus, setMirrorStatus] = useState<ReceiptMirrorStatus | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [copied, setCopied] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      clearLegacySurveyStorage(localStorage);
      clearDraftStorage(localStorage);
      clearLegacySurveyStorage(sessionStorage);
      const receipt = loadReceipt(localStorage);
      if (receipt) {
        saveReceipt(localStorage, receipt);
        setLastResponse(receipt.response);
        setCredential(receipt.credential);
        setMirrorStatus(receipt.mirrorStatus);
        clearDraftStorage(sessionStorage);
        setView("thanks");
      } else {
        const draft = loadDraft(sessionStorage);
        if (draft) {
          setForm(draft.form);
          setCredential(draft.credential);
        } else {
          setCredential(createSubmissionCredential());
        }
      }
      setHydrated(true);
    }, 0);
    return () => window.clearTimeout(handle);
  }, []);

  useEffect(() => {
    if (!hydrated || view !== "survey" || !credential) return;
    if (form.privacyConsent) saveDraft(sessionStorage, { form, credential });
    else clearDraftStorage(sessionStorage);
  }, [credential, form, hydrated, view]);

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const validationMessage = () => {
    if (step === 0 && (!form.stage || !form.platforms.length || !form.monthlyPosts)) return "현재 단계, 관심 플랫폼, 월 게시량을 선택해주세요.";
    if (step === 1 && (!form.bottlenecks.length || !form.desiredPosts || !form.tools.length || !form.controlPreference)) return "병목, 목표 게시량, 사용 도구, 승인 방식을 선택해주세요.";
    if (step === 2 && (!form.priceReaction || !form.comfortablePrice || !form.valuedBundle.length || !form.purchaseBlockers.length || !form.purchaseTiming)) return "가격 반응과 구매 조건을 빠짐없이 선택해주세요.";
    if (step === 3 && (!form.courseTopics.length || !form.support.length || !form.liveTime || !form.desiredOutcome.trim())) return "강의 주제, 지원 방식, 라이브 시간, 14일 목표를 입력해주세요.";
    if (step === 4 && (!form.buyCondition.trim() || !form.painWords.trim())) return "구매 조건과 실제 불만 문장을 입력해주세요.";
    if (step === 4 && !form.fullName.trim()) return "사전조사 접수에 사용할 이름을 입력해주세요.";
    if (step === 4 && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/u.test(form.email.trim())) return "접수에 사용할 이메일을 정확히 입력해주세요.";
    if (step === 4 && Boolean(form.contactMethod) !== Boolean(form.contact.trim())) return "추가 연락처와 연락 방법을 함께 입력해주세요.";
    if (step === 4 && !form.privacyConsent) return "개인정보 수집·이용 필수 동의를 확인해주세요.";
    return "";
  };

  const next = () => {
    const message = validationMessage();
    if (message) {
      setError(message);
      document.querySelector(".survey-card")?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    setError("");
    setStep((current) => Math.min(4, current + 1));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const submit = async () => {
    const message = validationMessage();
    if (message) {
      setError(message);
      return;
    }
    const activeCredential = credential ?? createSubmissionCredential();
    if (!credential) setCredential(activeCredential);
    const submission = validateSurveySubmission({ ...form, ...activeCredential });
    if (!submission.ok) {
      setError(submission.message);
      return;
    }

    // Persist the stable ID and withdrawal proof before the network request. A retry
    // after an ambiguous response therefore reuses the same logical submission.
    saveDraft(sessionStorage, { form: formFromSubmission(submission.value), credential: activeCredential });
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      const result = await fetch("/api/reservations", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(submission.value),
      });
      const body = await result.json().catch(() => null) as SubmissionApiResponse | null;
      if (!result.ok) throw new Error(body?.message || "사전조사 저장에 실패했습니다.");
      if (!isSurveyResponse(body?.response)) throw new Error("서버 접수 결과 형식이 올바르지 않습니다.");
      if (body.mirrorStatus !== "pending" && body.mirrorStatus !== "mirrored") throw new Error("서버 동기화 상태 형식이 올바르지 않습니다.");
      const summary = receiptSummary(body.response);
      if (!summary) throw new Error("서버 접수 요약 형식이 올바르지 않습니다.");

      setLastResponse(body.response);
      setCredential(activeCredential);
      setMirrorStatus(body.mirrorStatus);
      const locallySaved = saveReceipt(localStorage, { response: summary, credential: activeCredential, mirrorStatus: body.mirrorStatus });
      if (locallySaved) clearDraftStorage(sessionStorage);
      setNotice(
        !locallySaved
          ? "접수는 완료됐지만 완료 확인 정보를 새로 저장하지 못했습니다. 이 창을 닫기 전에 응답 ID를 복사하거나 철회 기능을 사용해주세요."
          : body.mirrorStatus === "pending"
            ? "접수는 완료됐습니다. 분석용 사본 동기화는 다음 재시도에서 이어집니다."
            : "",
      );
      setView("thanks");
      window.scrollTo({ top: 0 });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "사전조사 저장에 실패했습니다. 잠시 후 다시 시도해주세요.");
      document.querySelector(".survey-card")?.scrollIntoView({ behavior: "smooth" });
    } finally {
      setSubmitting(false);
    }
  };

  const retryMirrorSync = async () => {
    if (!lastResponse || !credential || mirrorStatus !== "pending") return;
    if (isReceiptExpired(lastResponse)) {
      discardExpiredReceipt();
      return;
    }
    const originalCreatedAt = lastResponse.createdAt;
    setSyncing(true);
    setNotice("");
    try {
      const result = await fetch("/api/reservations", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(credential),
      });
      const body = await result.json().catch(() => null) as SubmissionApiResponse | null;
      if (!result.ok) throw new Error(body?.message || "분석용 사본 동기화에 실패했습니다.");
      const summary = receiptSummary(body?.response);
      if (!summary || summary.id !== credential.id) throw new Error("서버 접수 결과 형식이 올바르지 않습니다.");
      if (summary.createdAt !== originalCreatedAt) throw new Error("서버가 원래 접수 시각과 다른 결과를 반환했습니다.");
      const nextMirrorStatus = body?.mirrorStatus;
      if (nextMirrorStatus !== "pending" && nextMirrorStatus !== "mirrored") throw new Error("서버 동기화 상태 형식이 올바르지 않습니다.");
      if (isReceiptExpired(summary)) {
        discardExpiredReceipt();
        return;
      }

      setLastResponse((current) => current && isSurveyResponse(current) ? current : summary);
      setMirrorStatus(nextMirrorStatus);
      const locallySaved = saveReceipt(localStorage, { response: summary, credential, mirrorStatus: nextMirrorStatus });
      if (nextMirrorStatus === "mirrored") {
        if (locallySaved) clearDraftStorage(sessionStorage);
        setNotice(locallySaved ? "분석용 사본 동기화를 완료했습니다." : "동기화는 완료됐지만 완료 확인 정보를 브라우저에 갱신하지 못했습니다.");
      } else {
        setNotice(locallySaved ? "분석용 사본 동기화가 아직 대기 중입니다. 같은 버튼으로 다시 시도할 수 있습니다." : "동기화가 대기 중이며 완료 확인 정보를 브라우저에 갱신하지 못했습니다.");
      }
    } catch (syncError) {
      setNotice(syncError instanceof Error ? syncError.message : "분석용 사본 동기화에 실패했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setSyncing(false);
    }
  };

  const copyResponseId = async () => {
    if (!lastResponse) return;
    try {
      await navigator.clipboard.writeText(lastResponse.id);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setNotice(`클립보드에 복사하지 못했습니다. 응답 ID: ${lastResponse.id}`);
    }
  };

  const discardExpiredReceipt = () => {
    clearSurveyStorage(localStorage);
    clearSurveyStorage(sessionStorage);
    setForm(initialForm);
    setCredential(createSubmissionCredential());
    setLastResponse(null);
    setMirrorStatus(null);
    setStep(0);
    setView("survey");
    setNotice("개인정보 보유 기간이 끝나 브라우저의 완료 정보와 초안을 삭제했습니다.");
    window.scrollTo({ top: 0 });
  };

  const withdraw = async () => {
    if (!lastResponse || !credential || !window.confirm("서버와 분석용 사본에서 이 설문 응답을 철회할까요? 이 작업은 되돌릴 수 없습니다.")) return;
    setWithdrawing(true);
    setNotice("");
    try {
      const result = await fetch("/api/reservations", {
        method: "DELETE",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(credential),
      });
      const body = await result.json().catch(() => null) as { message?: string } | null;
      if (!result.ok) throw new Error(body?.message || "응답 철회에 실패했습니다.");
      clearSurveyStorage(localStorage);
      clearSurveyStorage(sessionStorage);
      setForm(initialForm);
      setCredential(createSubmissionCredential());
      setLastResponse(null);
      setMirrorStatus(null);
      setStep(0);
      setView("survey");
      setNotice("응답 철회를 완료했습니다.");
      window.scrollTo({ top: 0 });
    } catch (withdrawError) {
      setNotice(withdrawError instanceof Error ? withdrawError.message : "응답 철회에 실패했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setWithdrawing(false);
    }
  };

  const startNew = () => {
    if (lastResponse) {
      setNotice("기존 응답의 철회 증명을 잃지 않도록 새 응답 작성을 막았습니다. 먼저 내 응답 철회를 완료해주세요.");
      setView("thanks");
      window.scrollTo({ top: 0 });
      return;
    }
    clearSurveyStorage(localStorage);
    clearSurveyStorage(sessionStorage);
    setForm(initialForm);
    setCredential(createSubmissionCredential());
    setLastResponse(null);
    setMirrorStatus(null);
    setStep(0);
    setError("");
    setNotice("");
    setView("survey");
  };

  return (
    <main>
      <header className="topbar">
        <button className="brand" onClick={startNew} type="button"><span>TA</span><strong>THREAD AUTO</strong><small>개인 강의 사전조사</small></button>
        <nav aria-label="주요 링크">
          <button className="active" onClick={startNew} type="button">강의 사전조사</button>
          <a className="service-nav-link" href="https://coupuas-thread-auto-ten.vercel.app/" target="_blank" rel="noreferrer" aria-label="운영 중인 THREAD AUTO 서비스 새 창에서 바로 사용하기">실제 서비스 바로 사용 <span aria-hidden="true">↗</span></a>
        </nav>
      </header>

      {notice && <div className="global-notice" role="status" aria-live="polite">{notice}</div>}

      {view === "survey" && (
        <>
          <section className="hero">
            <div className="hero-copy">
              <div className="eyebrow">실제 서비스 운영 중 · 개인 강의 사전조사</div>
              <h1>프로그램은 지금 바로.<br /><em>강의는 필요한 것부터.</em></h1>
              <p>THREAD AUTO 프로그램은 지금 바로 이용할 수 있습니다. 이 페이지는 1년 사용권·개인 강의·원격 과외·사용법 PDF를 묶은 70만원 강의 패키지를 실제 질문과 병목에 맞게 구성하기 위한 사전조사입니다.</p>
              <a className="service-link-card" href="https://coupuas-thread-auto-ten.vercel.app/" target="_blank" rel="noreferrer">
                <span><b>LIVE</b><small>이미 운영 중인 THREAD AUTO</small><strong>실제 서비스 웹사이트에서 바로 사용하기</strong></span><em>접속하기 ↗</em>
              </a>
              <div className="reservation-facts" aria-label="강의 사전조사 안내">
                <span><b>0원</b> 지금 결제 없음</span>
                <span><b>안전</b> 응답 ID 기준 재시도</span>
                <span><b>4분</b> 강의 맞춤 조사</span>
              </div>
              <div className="trial-benefit" role="note">
                <b>접수</b>
                <div><span>강의 사전조사 참여</span><strong>응답 ID로 접수 상태 확인</strong><small>혜택 발급을 확정하거나 구매를 약속하는 절차가 아닙니다.</small></div>
              </div>
              <div className="offer-strip"><span>검토 중인 구성</span><strong>1년 사용권 + 개인 강의 + 원격 도움 + PDF</strong><b>700,000원</b></div>
            </div>
            <aside className="hero-proof">
              <span className="proof-number">7</span><strong>개 쇼핑 제휴 플랫폼</strong>
              <p>쿠팡뿐 아니라 네이버·토스·오늘의집·무신사·컬리·올리브영까지 관심도를 나눠 확인합니다.</p>
              <div className="proof-flow" aria-label="서비스 흐름"><span>링크</span><i aria-hidden="true">→</i><span>문안</span><i aria-hidden="true">→</i><span>검수</span><i aria-hidden="true">→</i><span>게시</span></div>
            </aside>
          </section>

          <section className="survey-shell">
            <aside className="step-rail">
              <div className="progress-caption"><span>진행률</span><strong>{step + 1} / 5</strong></div>
              <div className="progress-track" role="progressbar" aria-label="설문 진행률" aria-valuemin={1} aria-valuemax={5} aria-valuenow={step + 1}><span style={{ width: `${((step + 1) / 5) * 100}%` }} /></div>
              {steps.map((item, index) => (
                <button type="button" key={item.eyebrow} disabled={index > step} className={`${index === step ? "current" : ""} ${index < step ? "done" : ""}`} onClick={() => setStep(index)}>
                  <b aria-hidden="true">{index < step ? "✓" : index + 1}</b><span>{item.eyebrow}</span>
                </button>
              ))}
              <div className="privacy-note"><strong>조사 전 확인</strong><p>강의 사전조사는 구매 계약이나 결제가 아닙니다. 수익·조회·구매 전환을 보장하지 않습니다.</p></div>
            </aside>

            <div className="survey-card">
              <div className="section-intro"><span>{steps[step].eyebrow}</span><h2>{steps[step].title}</h2><p>{steps[step].note}</p></div>
              {error && <div className="error-box" role="alert">{error}</div>}

              {step === 0 && <>
                <Question number="01" title="현재 쇼핑 제휴 콘텐츠 운영 단계는 어디인가요?"><ChoiceGrid label="현재 운영 단계" options={stages} value={form.stage} onChange={(value) => update("stage", value)} /></Question>
                <Question number="02" title="관심 있거나 사용 중인 플랫폼을 모두 선택해주세요" description="플랫폼별 강의·지원 우선순위를 결정합니다."><MultiChoice label="관심 플랫폼" options={platforms} values={form.platforms} onChange={(value) => update("platforms", value)} /></Question>
                <Question number="03" title="현재 한 달에 몇 개 정도 게시하나요?"><ChoiceGrid label="월 게시량" options={monthlyPostOptions} value={form.monthlyPosts} onChange={(value) => update("monthlyPosts", value)} /></Question>
                <Question number="04" title="현재 하시는 일과 제휴 수익 경험을 알려주세요" description="선택 응답이며 타깃 세분화에만 사용합니다.">
                  <div className="two-fields"><label>현재 일·업종<input maxLength={120} value={form.occupation} onChange={(event) => update("occupation", event.target.value)} placeholder="예: 직장인, 자영업, 콘텐츠 크리에이터" /></label><label>제휴 수익 경험<input maxLength={200} value={form.revenueExperience} onChange={(event) => update("revenueExperience", event.target.value)} placeholder="예: 아직 없음, 월 5만원 내외" /></label></div>
                </Question>
              </>}

              {step === 1 && <>
                <Question number="05" title="가장 힘들거나 오래 걸리는 단계를 모두 골라주세요"><MultiChoice label="작업 병목" options={bottlenecks} values={form.bottlenecks} onChange={(value) => update("bottlenecks", value)} /></Question>
                <Question number="06" title="게시물 1개를 수작업으로 만드는 데 몇 분 걸리나요?" description="상품 선택부터 최종 게시까지 실제 평균 시간을 넣어주세요.">
                  <label className="range-label" htmlFor="manual-minutes">게시물 1개당 수작업 시간</label>
                  <div className="range-wrap"><input id="manual-minutes" type="range" min="5" max="180" step="5" value={form.manualMinutes} onChange={(event) => update("manualMinutes", Number(event.target.value))} /><output htmlFor="manual-minutes">{form.manualMinutes}<small>분</small></output></div>
                </Question>
                <Question number="07" title="자동화가 된다면 하루 몇 개를 꾸준히 올리고 싶나요?"><ChoiceGrid label="하루 목표 게시량" options={desiredPostOptions} value={form.desiredPosts} onChange={(value) => update("desiredPosts", value)} /></Question>
                <Question number="08" title="이미 시도해본 방법이나 도구가 있나요?"><MultiChoice label="사용 경험이 있는 도구" options={toolOptions} values={form.tools} onChange={(value) => update("tools", value)} /></Question>
                <Question number="09" title="자동화의 마지막 게시 단계는 어떻게 원하시나요?"><ChoiceGrid label="게시 승인 방식" options={controlPreferenceOptions} value={form.controlPreference} onChange={(value) => update("controlPreference", value)} /></Question>
              </>}

              {step === 2 && <>
                <Question number="10" title="현재 구성에 대한 구매 의향은 몇 점인가요?" description="프로그램 1년 + 개인 강의 + 원격 도움 + PDF, 총 70만원 기준입니다.">
                  <div className="intent-scale" role="radiogroup" aria-label="구매 의향 점수">{Array.from({ length: 11 }, (_, number) => <label key={number} className={form.intent === number ? "selected" : ""}><input className="choice-native" type="radio" name="구매 의향 점수" value={number} checked={form.intent === number} onChange={() => update("intent", number)} /><span>{number}</span></label>)}</div>
                  <div className="scale-label"><span>전혀 없음</span><strong>{form.intent}점</strong><span>매우 높음</span></div>
                </Question>
                <Question number="11" title="70만원 가격을 보면 가장 가까운 반응은 무엇인가요?"><ChoiceGrid label="가격 반응" options={priceReactionOptions} value={form.priceReaction} onChange={(value) => update("priceReaction", value)} /></Question>
                <Question number="12" title="심리적으로 편한 결제 범위는 어디인가요?"><ChoiceGrid label="편한 결제 범위" options={comfortablePriceOptions} value={form.comfortablePrice} onChange={(value) => update("comfortablePrice", value)} /></Question>
                <Question number="13" title="가격을 판단할 때 중요한 포함 항목을 골라주세요"><MultiChoice label="중요 포함 항목" options={bundleItems} values={form.valuedBundle} onChange={(value) => update("valuedBundle", value)} /></Question>
                <Question number="14" title="구매를 가장 망설이게 하는 이유를 모두 골라주세요"><MultiChoice label="구매 방해 요소" options={purchaseBlockers} values={form.purchaseBlockers} onChange={(value) => update("purchaseBlockers", value)} /></Question>
                <Question number="15" title="조건이 맞는다면 언제 시작하고 싶나요?"><ChoiceGrid label="구매 시기" options={purchaseTimingOptions} value={form.purchaseTiming} onChange={(value) => update("purchaseTiming", value)} /></Question>
                <Question number="16" title="선호하는 결제 방식이 있나요?" description="선택 응답입니다."><ChoiceGrid label="결제 방식" options={paymentPreferenceOptions} value={form.paymentPreference} onChange={(value) => update("paymentPreference", value)} /></Question>
              </>}

              {step === 3 && <>
                <Question number="17" title="개인 강의에서 꼭 다뤄야 할 주제를 최대 3개 골라주세요" description={`${form.courseTopics.length}/3 선택`}><MultiChoice label="강의 주제" options={courseTopics} values={form.courseTopics} max={3} onChange={(value) => update("courseTopics", value)} /></Question>
                <Question number="18" title="사용 중 막혔을 때 필요한 지원을 골라주세요"><MultiChoice label="필요한 지원 방식" options={supportOptions} values={form.support} onChange={(value) => update("support", value)} /></Question>
                <Question number="19" title="무료 라이브에 참여하기 좋은 시간은 언제인가요?"><ChoiceGrid label="라이브 참여 시간" options={liveTimeOptions} value={form.liveTime} onChange={(value) => update("liveTime", value)} /></Question>
                <Question number="20" title="사용 후 14일 안에 어떤 결과가 남으면 만족할까요?" description="수익 보장보다 실제 실행 결과를 적어주세요."><textarea id="desired-outcome" aria-labelledby="question-20" maxLength={1000} value={form.desiredOutcome} onChange={(event) => update("desiredOutcome", event.target.value)} placeholder="예: 설치를 끝내고 7개 플랫폼 중 2곳에서 매일 3개씩 게시하는 루틴을 만들고 싶다" rows={4} /></Question>
              </>}

              {step === 4 && <>
                <Question number="21" title="어떤 증거 또는 조건이 있으면 70만원을 결제할 수 있나요?"><textarea id="buy-condition" aria-labelledby="question-21" maxLength={1000} value={form.buyCondition} onChange={(event) => update("buyCondition", event.target.value)} placeholder="예: 내 계정에서 실제로 첫 게시까지 되는 화면, 원격지원 응답 범위, 환불 조건" rows={4} /></Question>
                <Question number="22" title="지금 가장 짜증나는 순간을 평소 말투로 한 문장만 적어주세요" description="이 문장이 실제 마케팅 훅과 강의 사례에 가장 큰 도움이 됩니다."><textarea id="pain-words" aria-labelledby="question-22" maxLength={1000} value={form.painWords} onChange={(event) => update("painWords", event.target.value)} placeholder="예: 링크는 만들었는데 또 글 쓰고 이미지 만들 생각을 하니 그냥 오늘도 안 올리게 돼요" rows={4} /></Question>
                <Question number="23" title="사전조사 접수 정보를 입력해주세요" description="이메일은 접수 연락과 남용 방지에 사용하며, 선택한 경우에만 인터뷰·서비스 소식을 안내합니다.">
                  <div className="two-fields identity-fields"><label>이름 <b className="required-mark">필수</b><input required maxLength={80} value={form.fullName} onChange={(event) => update("fullName", event.target.value)} placeholder="홍길동" autoComplete="name" /></label><label>이메일 <b className="required-mark">필수</b><input required maxLength={254} type="email" value={form.email} onChange={(event) => update("email", event.target.value)} placeholder="name@example.com" autoComplete="email" /></label></div>
                  <div className="benefit-terms"><strong>재시도 기준</strong><span>같은 응답 ID와 철회 증명은 중복 저장하지 않음</span><small>사전조사 접수는 무료 이용권 발급이나 구매 계약을 의미하지 않습니다. 이메일 소유권을 확인하거나 이메일별 혜택을 부여하지 않습니다.</small></div>
                  <div className="optional-contact"><strong>인터뷰용 추가 연락처 <small>선택</small></strong><div className="two-fields"><label>연락 방법<select value={form.contactMethod} onChange={(event) => update("contactMethod", event.target.value)}>{contactMethodOptions.map((option) => <option key={option || "none"} value={option}>{option || "선택 안 함"}</option>)}</select></label><label>아이디·전화번호<input maxLength={100} value={form.contact} onChange={(event) => update("contact", event.target.value)} placeholder="선택 입력" autoComplete="tel" /></label></div></div>
                  <div className="consent-row"><input id="interview-consent" type="checkbox" checked={form.interview} onChange={(event) => update("interview", event.target.checked)} /><span><label htmlFor="interview-consent">15분 인터뷰 참여 가능</label><small>설치·강의·가격에 대해 더 자세히 이야기할 수 있습니다.</small></span></div>
                  <div className="consent-row"><input id="marketing-consent" type="checkbox" checked={form.marketingConsent} onChange={(event) => update("marketingConsent", event.target.checked)} /><span><label htmlFor="marketing-consent">[선택] 서비스·강의 안내 이메일 수신 동의</label><small>기능 소식과 개인 강의 일정을 이메일로 안내합니다. 동의하지 않아도 설문 제출에는 영향이 없습니다.</small></span></div>
                  <div className="consent-row required"><input id="privacy-consent" required type="checkbox" checked={form.privacyConsent} onChange={(event) => update("privacyConsent", event.target.checked)} /><span><label htmlFor="privacy-consent">[필수] 개인정보 수집·이용에 동의합니다</label><small><b>수집·이용 주체</b> THREAD AUTO · <b>수집 항목</b> 이름, 이메일, 설문 응답 및 선택 입력 연락처<br /><b>이용 목적</b> 개인 강의 사전조사와 선택한 후속 안내 · <b>보유 기간</b> 제출일로부터 최대 1년<br />완료 화면의 철회 기능으로 중앙 응답과 분석용 사본 삭제를 요청할 수 있습니다. Google Sheets 분석용 사본에는 이름·이메일·연락처와 자유서술 답변을 보내지 않습니다. 동의를 거부할 수 있으나 설문은 제출할 수 없습니다. 만 14세 미만은 참여하지 마세요.</small></span></div>
                </Question>
              </>}

              <div className="form-actions">
                <button type="button" className="back" disabled={step === 0 || submitting} onClick={() => { setError(""); setStep((current) => Math.max(0, current - 1)); }}>이전</button>
                {step < 4
                  ? <button type="button" className="primary" onClick={next}>다음 질문 <span aria-hidden="true">→</span></button>
                  : <button type="button" className="primary submit" disabled={submitting || !hydrated} onClick={submit}>{submitting ? "사전조사를 저장하는 중…" : "강의 사전조사 제출"} <span aria-hidden="true">{submitting ? "" : "✓"}</span></button>}
              </div>
            </div>
          </section>
        </>
      )}

      {view === "thanks" && lastResponse && (
        <section className="thanks-page">
          <div className="success-mark" aria-hidden="true">✓</div>
          <div className="eyebrow">개인 강의 사전조사 접수 완료</div>
          <h1>강의에 필요한 내용을<br />안전하게 접수했습니다.</h1>
          <p>답변해주신 병목, 구매 조건, 원하는 강의 주제를 제품·강의·원격지원 구성에 반영합니다.</p>
          <div className="trial-confirmation"><b>신청 접수 완료</b><span>{isSurveyResponse(lastResponse) ? <><strong>{lastResponse.fullName}</strong>님의 응답과 연락 이메일 <em>{lastResponse.email}</em>을 접수했습니다.</> : <>응답 ID와 철회 증명을 이용해 접수 상태를 안전하게 복구했습니다.</>}</span><small>이 사전조사는 유료 구매 계약이나 무료 이용권 발급 확정이 아니며 지금 결제되는 금액은 없습니다.</small></div>
          {isSurveyResponse(lastResponse) && <div className="personal-result">
            <div><span>강의 관심도</span><strong>{lastResponse.demandScore}<small>/100</small></strong></div>
            <div><span>현재 분류</span><strong>{lastResponse.segment}</strong></div>
            <div><span>가장 큰 병목</span><strong>{lastResponse.bottlenecks[0]}</strong></div>
          </div>}
          {isSurveyResponse(lastResponse) && <div className="result-note">이 점수는 수익 가능성이나 구매 자격을 의미하지 않습니다. 작업량·긴급도·구매 의향을 후속 조사 우선순위로 정리한 값입니다.</div>}
          {mirrorStatus === "pending" && <div className="result-note mirror-status" role="status">중앙 접수는 완료됐지만 개인정보를 제외한 분석용 사본 동기화가 대기 중입니다. 아래 버튼으로 같은 응답을 안전하게 다시 동기화할 수 있습니다.</div>}
          <p className="response-id"><strong>응답 ID</strong><code>{lastResponse.id}</code></p>
          <div className="thanks-actions">
            {mirrorStatus === "pending" && <button type="button" className="ghost" disabled={syncing || withdrawing} onClick={retryMirrorSync}>{syncing ? "동기화 재시도 중…" : "분석용 사본 다시 동기화"}</button>}
            <button type="button" className="primary" onClick={copyResponseId}>{copied ? "복사 완료" : "응답 ID 복사"}</button>
            <button type="button" className="danger" disabled={withdrawing || syncing} onClick={withdraw}>{withdrawing ? "철회 처리 중…" : "내 응답 철회"}</button>
          </div>
        </section>
      )}

      <footer><strong>THREAD AUTO</strong><span>개인 강의 사전조사 · 실제 서비스 운영 중</span><p>수익·조회·구매 전환을 보장하지 않습니다.</p></footer>
    </main>
  );
}
