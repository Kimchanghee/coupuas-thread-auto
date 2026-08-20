const concepts = {
  1: "기존 다크 테마를 정돈한 운영 콘솔 · shadcn/Radix 원칙",
  2: "밝고 친숙한 Windows 생산성 도구 · Fluent/MUI 원칙",
  3: "상태 판독을 최우선으로 한 관제 화면 · Ant Design 원칙",
  4: "초보자 실수를 줄이는 단계별 집중 흐름",
  5: "대형 모니터 활용도가 높은 12열 모듈 대시보드",
};

const params = new URLSearchParams(window.location.search);
const requested = Number(params.get("concept"));
let current = requested >= 1 && requested <= 5 ? requested : 1;

if (params.get("clean") === "1") {
  document.body.classList.add("clean-preview");
}

function selectConcept(number, updateUrl = true) {
  current = number;
  document.body.dataset.concept = String(number);
  document.querySelector("#concept-description").textContent = concepts[number];
  document.querySelectorAll("[data-select]").forEach((button) => {
    button.setAttribute("aria-selected", String(Number(button.dataset.select) === number));
  });
  document.title = `${String(number).padStart(2, "0")} · ${concepts[number].split(" · ")[0]} | UI 시안`;
  if (updateUrl) {
    const next = new URL(window.location.href);
    next.searchParams.set("concept", String(number));
    window.history.replaceState({}, "", next);
  }
}

document.querySelectorAll("[data-select]").forEach((button) => {
  button.addEventListener("click", () => selectConcept(Number(button.dataset.select)));
});

window.addEventListener("keydown", (event) => {
  if (event.altKey && /^[1-5]$/.test(event.key)) {
    event.preventDefault();
    selectConcept(Number(event.key));
  }
});

selectConcept(current, false);
