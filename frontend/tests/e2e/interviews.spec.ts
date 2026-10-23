import { expect, test, type Page } from "@playwright/test";

test.use({ launchOptions: { args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] }, permissions: ["camera", "microphone"] });
const id = "00000000-0000-4000-8000-000000009123";
const cors = { "Access-Control-Allow-Origin": "http://localhost:3000", "Access-Control-Allow-Credentials": "true", "Access-Control-Allow-Headers": "content-type", "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS" };
const evaluation = { score: 80, accuracy: 80, relevance: 90, clarity: 70, feedback: "Your retry example is specific; explain the transaction boundary as well.", strengths: ["Specific example"], weaknesses: ["Transaction scope missing"], corrections: ["Use an atomic write"], sample_answer: "I would use an idempotency key with an atomic transaction.", recommendations: ["Practice tracing a retry failure"], follow_up: "What happens with two workers?" };
function session() { return { id, role: "Backend engineer", interview_type: "technical", difficulty: 2, duration_minutes: 15, question_count: 2, status: "active", elapsed_seconds: 0, revision: 1, model: "test-provider", created_at: new Date().toISOString(), report: { score: null as number | null, accuracy: null as number | null, relevance: null as number | null, clarity: null as number | null, answered: 0, planned: 2, strengths: [] as string[], weaknesses: [] as string[], recommendations: [] as string[], note: "AI practice estimates, not hiring predictions." }, turns: [{ id: "00000000-0000-4000-8000-000000000001", text: "How do you make the Python worker retry-safe?", category: "technical", difficulty: 2, answer: undefined as string | undefined, evaluation: undefined as typeof evaluation | undefined }] }; }

async function api(page: Page, configured = true) {
  const value = session(); const creates: unknown[] = []; let failAnswer = false;
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname; const method = route.request().method();
    if (method === "OPTIONS") return route.fulfill({ headers: cors, status: 204 });
    let json: unknown = {};
    if (path.endsWith("/auth/me")) json = { id: "user", full_name: "Test owner" };
    else if (path.endsWith("/capabilities")) json = { configured, provider: "gemini" };
    else if (path.endsWith("/resumes")) json = [{ id: "resume-one", name: "My backend resume" }];
    else if (path.endsWith("/interviews") && method === "GET") json = [];
    else if (path.endsWith("/interviews") && method === "POST") { creates.push(route.request().postDataJSON()); json = value; }
    else if (path.endsWith("/answers")) {
      if (failAnswer) return route.fulfill({ headers: cors, status: 503, json: { detail: "Provider temporarily unavailable. Retry shortly." } });
      value.turns.at(-1)!.answer = route.request().postDataJSON().answer; value.turns.at(-1)!.evaluation = evaluation;
      value.report = { ...value.report, score: 80, accuracy: 80, relevance: 90, clarity: 70, answered: value.turns.length, strengths: evaluation.strengths, weaknesses: evaluation.weaknesses, recommendations: evaluation.recommendations };
      if (value.turns.length === 2) value.status = "completed";
      json = value;
    } else if (path.endsWith("/next")) {
      value.turns.push({ id: "00000000-0000-4000-8000-000000000002", text: "How would you test two concurrent workers with the same key?", category: "technical", difficulty: 2, answer: undefined, evaluation: undefined }); json = value;
    } else if (path.endsWith("/control")) {
      const action = route.request().postDataJSON().action;
      value.status = action === "pause" ? "paused" : action === "resume" ? "active" : "completed"; json = value;
    } else if (path.endsWith("/retake")) json = { ...session(), id: "00000000-0000-4000-8000-000000009124" };
    else if (path.endsWith(`/${id}`)) json = value;
    else if (path.endsWith("/00000000-0000-4000-8000-000000009124")) json = { ...session(), id: "00000000-0000-4000-8000-000000009124" };
    return route.fulfill({ headers: cors, json });
  });
  return { value, creates, fail: (state: boolean) => { failAnswer = state; } };
}

test("configure interview, submit answers, get follow-up and report", async ({ page }, info) => {
  const mock = await api(page);
  await page.goto("/interviews");
  await page.getByLabel("Target job role", { exact: true }).fill("Backend engineer");
  await page.getByRole("button", { name: "Start interview", exact: true }).click();
  await expect(page).toHaveURL(`/interviews/${id}`);
  await page.screenshot({ path: `test-results/interview-room-${info.project.name}.png`, fullPage: true });
  expect(mock.creates[0]).toMatchObject({ role: "Backend engineer", resume_id: "resume-one" });
  await page.getByLabel("Your answer", { exact: true }).fill("I use idempotency keys and atomic transactions to make writes safe to retry.");
  await page.getByRole("button", { name: "Submit answer", exact: true }).click();
  await expect(page.getByText("Answer saved · 80/100")).toBeVisible();
  await page.getByRole("button", { name: "Next question", exact: true }).click();
  await expect(page.getByRole("heading", { name: "How would you test two concurrent workers with the same key?" })).toBeVisible();
  await page.getByLabel("Your answer", { exact: true }).fill("I synchronize two workers with a barrier and assert one committed effect.");
  await page.getByRole("button", { name: "Submit answer", exact: true }).click();
  await expect(page).toHaveURL(`/interviews/${id}/report`);
  await expect(page.getByRole("heading", { name: "Your revision plan" })).toBeVisible();
  await expect(page.getByText("Practice tracing a retry failure").first()).toBeVisible();
  await page.getByText("Sample answer / suggested structure").first().click();
  await expect(page.getByText(evaluation.sample_answer).first()).toBeVisible();
  await page.screenshot({ path: `test-results/interview-report-${info.project.name}.png`, fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("webcam stream, permission fallback, pause and provider failures preserve text", async ({ page }) => {
  const mock = await api(page);
  await page.goto(`/interviews/${id}`);
  const camera = page.getByRole("button", { name: "Enable camera", exact: true });
  await camera.click();
  await expect(page.getByRole("button", { name: "Turn camera off", exact: true })).toBeVisible();
  await expect.poll(() => page.locator("video").evaluate(video => (video as HTMLVideoElement).srcObject instanceof MediaStream)).toBe(true);
  const text = "Keep this answer through a failed request.";
  await page.getByLabel("Your answer", { exact: true }).fill(text);
  mock.fail(true);
  await page.getByRole("button", { name: "Submit answer", exact: true }).click();
  await expect(page.getByText("Provider temporarily unavailable.", { exact: false })).toBeVisible();
  await expect(page.getByLabel("Your answer", { exact: true })).toHaveValue(text);
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(page.getByRole("button", { name: "Resume", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Enable camera", exact: true })).toBeDisabled();
  await expect.poll(() => page.locator("video").evaluate(video => (video as HTMLVideoElement).srcObject === null)).toBe(true);
  await page.getByRole("button", { name: "Resume", exact: true }).click();
  await page.evaluate(() => { navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException("Denied", "NotAllowedError")); });
  await page.getByRole("button", { name: "Enable camera", exact: true }).click();
  await expect(page.getByText("Camera unavailable or permission denied.", { exact: false })).toBeVisible();
  await expect(page.getByLabel("Your answer", { exact: true })).toHaveValue(text);
});

test("browser dictation transcript and spoken questions have controllable lifecycles", async ({ page }) => {
  await page.addInitScript(() => {
    class Recognition {
      onresult?: (event: unknown) => void; onend?: () => void;
      start() { this.onresult?.({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript: "I use a transaction and a unique key." } }] }); }
      stop() { this.onend?.(); } abort() { this.onend?.(); }
    }
    Object.defineProperty(window, "SpeechRecognition", { configurable: true, value: Recognition });
    Object.defineProperty(window, "speechSynthesis", { configurable: true, value: { cancel() {}, speak(utterance: SpeechSynthesisUtterance) { utterance.onstart?.(new Event("start") as SpeechSynthesisEvent); } } });
  });
  await api(page); await page.goto(`/interviews/${id}`);
  await page.getByRole("button", { name: "Read question aloud", exact: true }).click();
  await expect(page.getByRole("button", { name: "Stop speaking", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Stop speaking", exact: true }).click();
  await page.getByRole("button", { name: "Dictate answer", exact: true }).click();
  await expect(page.getByLabel("Your answer", { exact: true })).toHaveValue("I use a transaction and a unique key.");
  await expect(page.getByRole("button", { name: "Submit answer", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Stop dictation", exact: true }).click();
  await expect(page.getByRole("button", { name: "Submit answer", exact: true })).toBeEnabled();
});

test("missing AI credentials are explicit and do not start a fake interview", async ({ page }) => {
  const mock = await api(page, false);
  await page.goto("/interviews");
  await expect(page.getByText("AI interviews need a backend Gemini API key.", { exact: false })).toBeVisible();
  await page.getByLabel("Target job role", { exact: true }).fill("Engineer");
  await expect(page.getByRole("button", { name: "Start interview", exact: true })).toBeDisabled();
  expect(mock.creates).toHaveLength(0);
});

test("saved history and progress lead to reports and independent retakes", async ({ page }) => {
  const mock = await api(page);
  mock.value.status = "completed";
  mock.value.turns[0].answer = "My saved answer"; mock.value.turns[0].evaluation = evaluation;
  mock.value.report = { ...mock.value.report, score: 80, accuracy: 80, relevance: 90, clarity: 70, answered: 1 };
  await page.route("**/api/v1/interviews", route => route.request().method() === "GET" ? route.fulfill({ headers: cors, json: [mock.value] }) : route.fallback());
  await page.goto("/interviews");
  await expect(page.getByRole("img", { name: "Interview scores over time: 80" })).toBeVisible();
  await page.getByRole("link", { name: "View report", exact: false }).click();
  await expect(page.getByText("My saved answer")).toBeVisible();
  await page.getByRole("button", { name: "Retake with fresh questions", exact: true }).click();
  await expect(page).toHaveURL("/interviews/00000000-0000-4000-8000-000000009124");
  await expect(page.getByRole("heading", { name: "How do you make the Python worker retry-safe?" })).toBeVisible();
});

test("reloading another tab's progress does not apply an old draft to a new question", async ({ page }) => {
  const mock = await api(page);
  await page.goto(`/interviews/${id}`);
  await page.getByLabel("Your answer", { exact: true }).fill("My unsent draft for the original question.");
  mock.fail(true);
  await page.getByRole("button", { name: "Submit answer", exact: true }).click();
  await expect(page.getByText("Provider temporarily unavailable.", { exact: false })).toBeVisible();
  mock.value.turns.push({ id: "00000000-0000-4000-8000-000000000002", text: "A different question from another tab about cache eviction?", category: "technical", difficulty: 2, answer: undefined, evaluation: undefined });
  await page.getByRole("button", { name: "Reload saved progress", exact: true }).click();
  await expect(page.getByRole("heading", { name: "A different question from another tab about cache eviction?" })).toBeVisible();
  await expect(page.getByLabel("Your answer", { exact: true })).toHaveValue("");
  await page.getByText("Unsubmitted draft from an earlier question", { exact: true }).click();
  await expect(page.getByText("My unsent draft for the original question.", { exact: true })).toBeVisible();
});
