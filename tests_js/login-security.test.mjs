import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import vm from "node:vm";
import { proxyPasswordReset } from "../api/_lib/password-reset-proxy.mjs";
import { verifyPasswordResetCaptcha, isPasswordResetCaptchaConfigured } from "../api/_lib/password-reset-rate-limit.mjs";
process.env.PASSWORD_RESET_PROXY_SECRET = "offline-proxy-test-secret-at-least-32-characters";
const request = body => ({method:"POST", headers:{"content-type":"application/json","x-forwarded-for":"203.0.113.1"}, body});
const validBody = {identifier:"test@example.test",program_type:"stmaker"};

test("failed CAPTCHA never consumes victim delivery quota", async () => {
  let deliveries=0, queued=0, admissions=0;
  const dependencies = {
    rateLimitImpl: async ({phase}) => {
      if(phase === "admission") { admissions++; return {allowed:true}; }
      return {allowed: ++deliveries <= 3};
    },
    captchaImpl: async ({token}) => token === "valid",
    enqueueImpl: async () => {queued++;},
  };
  for(let i=0;i<3;i++) await proxyPasswordReset(request(validBody),"request",dependencies);
  const result = await proxyPasswordReset(request({...validBody,captcha_token:"valid"}),"request",dependencies);
  assert.equal(result.status,202);
  assert.equal(admissions,4);
  assert.equal(deliveries,1);
  assert.equal(queued,1);
});

test("confirm is limited before upstream even for changing valid-shaped tokens", async () => {
  let attempts=0, upstream=0;
  for(let i=0;i<12;i++) {
    const result=await proxyPasswordReset(request({token:String(i).padStart(43,"a"),password:"Correct Horse Battery 72"}),"confirm",{
      rateLimitImpl:async({phase})=>{assert.equal(phase,"confirm"); return {allowed:++attempts<=3};},
      fetchImpl:async()=>{upstream++;return new Response('{}',{status:400});},
    });
    assert.equal(result.status,i<3?400:429);
  }
  assert.equal(upstream,3);
});

test("confirm fails closed for missing IP or unavailable shared limiter", async () => {
  const body={token:"a".repeat(43),password:"Correct Horse Battery 72"};
  for(const req of [request(body),{...request(body),headers:{"content-type":"application/json"}}]) {
    let upstream=0;
    const result=await proxyPasswordReset(req,"confirm",{rateLimitImpl:async()=>{throw Error("offline")},fetchImpl:async()=>{upstream++;}});
    assert.equal(result.status,503); assert.equal(upstream,0);
  }
});

const env={TURNSTILE_SECRET_KEY:"private-test-secret",TURNSTILE_SITE_KEY:"public-test-key",TURNSTILE_EXPECTED_HOSTNAMES:"example.test"};
test("CAPTCHA is mandatory and bound to host and action", async () => {
  assert.equal(isPasswordResetCaptchaConfigured({}),false);
  await assert.rejects(verifyPasswordResetCaptcha({}, {env:{}}));
  assert.equal(await verifyPasswordResetCaptcha({}, {env}),false);
  for(const payload of [{success:true,action:"password_reset",hostname:"evil.test"},{success:true,action:"login",hostname:"example.test"},{success:false,action:"password_reset",hostname:"example.test"}]) {
    assert.equal(await verifyPasswordResetCaptcha({token:"token",ipAddress:"203.0.113.1"},{env,fetchImpl:async()=>new Response(JSON.stringify(payload))}),false);
  }
  assert.equal(await verifyPasswordResetCaptcha({token:"token",ipAddress:"203.0.113.1"},{env,fetchImpl:async()=>new Response(JSON.stringify({success:true,action:"password_reset",hostname:"example.test"}))}),true);
});

test("recovery browser sends CAPTCHA token and resets it after request failure", async()=>{
  let submit, widget, submitted, resetCount=0;
  const button={disabled:false}; const status={};
  const elements={"#submit-button":button,"#status":Object.assign(status,{dataset:{}}),"#identifier":{value:"test@example.test"},"#recovery-form":{reportValidity:()=>true,addEventListener:(_,cb)=>submit=cb}};
  const window={turnstile:{render:(_,config)=>{widget=config;return 0;},reset:()=>resetCount++}};
  const context={window,document:{body:{dataset:{recoveryPage:"request"}},querySelector:key=>elements[key],createElement:()=>({}),head:{appendChild:()=>{}}},fetch:async(url,options)=>{
    if(url.endsWith("config")) return {ok:true,json:async()=>({siteKey:"site-test"})};
    submitted=JSON.parse(options.body);return {ok:false,status:503,json:async()=>({message:"temporary"})};
  }};
  vm.runInNewContext(fs.readFileSync(new URL("../public/password-reset.js",import.meta.url),"utf8"),context);
  assert.equal(button.disabled,true);
  await window.recoveryCaptchaReady(); widget.callback("verified-token");
  await submit({preventDefault(){}});
  assert.equal(submitted.captcha_token,"verified-token");
  assert.equal(button.disabled,true); assert.equal(resetCount,1);
});
