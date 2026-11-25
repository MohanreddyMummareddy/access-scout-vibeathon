const form = document.querySelector("#planner");
const arrival = document.querySelector("#arrival");
const stepFree = document.querySelector("#step-free");
const status = document.querySelector("#status");
const result = document.querySelector("#result");
const buttons = form.querySelectorAll("button");
const labels = { available: "Available", closed: "Closed", blocked: "Has steps", uncertain: "Needs confirmation" };

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function render(plan) {
  const route = plan.recommendation;
  const title = route ? `Use ${route.name}` : "No confirmed route";
  const summary = element("article", "", route ? "summary" : "summary uncertain");
  summary.append(element("h2", title));
  if (route) {
    summary.append(element("p", `${route.walk}-minute walk · Gate closes at ${route.close}`));
  } else if (plan.question) {
    summary.append(element("p", "Ask the venue: " + plan.question));
  } else {
    summary.append(element("p", "Try another arrival time or ask the venue about other entrances."));
  }
  result.append(summary);
  for (const option of plan.routes) {
    const card = element("article", "", "route");
    card.append(
      element("h3", `${option.name} · ${labels[option.status]}`),
      element("p", option.reason)
    );
    const evidence = element("ul");
    for (const [segment, , source] of option.segments) {
      evidence.append(element("li", `${segment} — ${source}`));
    }
    card.append(evidence);
    result.append(card);
  }
  const trace = element("details", "", "trace");
  trace.append(element("summary", "How the agents checked this route"));
  const calls = element("ol");
  for (const action of plan.trace) {
    calls.append(element("li", `${action.agent} · ${action.tool} (${action.mode}) — ${action.observation}`));
  }
  trace.append(calls);
  result.append(trace);
  return title;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const context = { arrival: arrival.value, step_free: stepFree.checked };
  buttons.forEach((button) => { button.disabled = true; });
  result.replaceChildren();
  status.textContent = "Checking entrances…";
  try {
    const response = await fetch("/api/scout/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(context),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "The route check failed.");
    status.textContent = `Route check complete for ${context.arrival}. ${render(data)}.`;
  } catch (error) {
    status.textContent = error.message || "The route check failed. Try again.";
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
});

for (const button of form.querySelectorAll("[data-example]")) {
  button.addEventListener("click", () => {
    arrival.value = button.dataset.example;
    stepFree.checked = true;
    form.requestSubmit();
  });
}
