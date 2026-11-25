const form = document.querySelector("#visit");
const fileInput = document.querySelector("#guide-file");
const textInput = document.querySelector("#guide-text");
const uploadStatus = document.querySelector("#upload-status");
const status = document.querySelector("#visit-status");
const output = document.querySelector("#visit-result");
const submit = form.querySelector('button[type="submit"]');
const sample = [
  "Campus Spring Festival",
  "Venue: India Habitat Centre, New Delhi",
  "Gate A | 16:00–20:00 | stairs",
  "Gate B | 16:00–18:00 | step-free | entry only",
  "Gate C | 16:00–20:00",
  "Gate D | 18:00–20:00 | step-free | exit only",
  "Opening talk | 17:00–18:00",
  "Design workshop | 18:00–18:45",
  "Campus recital | 18:30–19:15",
  "Closing session | 19:15–20:00",
].join("\n");

document.querySelector("#fill-guide").addEventListener("click", () => {
  textInput.value = sample;
  uploadStatus.textContent = "Example guide loaded. These gate and session details are fictional.";
});

let ocrScript;
function loadOcr() {
  if (!ocrScript) {
    ocrScript = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js";
      script.onload = resolve;
      script.onerror = () => {
        ocrScript = undefined;
        reject(new Error("Image text tools could not load. Try again or paste the guide text."));
      };
      document.head.append(script);
    });
  }
  return ocrScript;
}

async function recognize(image) {
  const worker = await createOcrWorker();
  try {
    const { data } = await worker.recognize(image);
    return data.text;
  } finally {
    await worker.terminate();
  }
}

async function createOcrWorker() {
  await loadOcr();
  return window.Tesseract.createWorker("eng", 1);
}

async function readPdf(file) {
  const base = "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/";
  const pdfjs = await import(base + "pdf.min.mjs");
  pdfjs.GlobalWorkerOptions.workerSrc = base + "pdf.worker.min.mjs";
  const documentTask = pdfjs.getDocument({ data: await file.arrayBuffer(), isEvalSupported: false });
  let worker;
  try {
    const pdf = await documentTask.promise;
    const pages = [];
    for (let index = 1; index <= Math.min(pdf.numPages, 4); index += 1) {
      const page = await pdf.getPage(index);
      const layer = await page.getTextContent();
      let text = layer.items.map((item) => item.str + (item.hasEOL ? "\n" : " ")).join("");
      if (!text.trim()) {
        const canvas = document.createElement("canvas");
        const original = page.getViewport({ scale: 1 });
        const scale = Math.min(2, 1800 / Math.max(original.width, original.height));
        const viewport = page.getViewport({ scale });
        canvas.width = Math.ceil(viewport.width);
        canvas.height = Math.ceil(viewport.height);
        await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
        worker ??= await createOcrWorker();
        const { data } = await worker.recognize(canvas);
        text = data.text;
      }
      pages.push(text);
    }
    return { text: pages.join("\n"), limited: pdf.numPages > 4 };
  } finally {
    await Promise.all([documentTask.destroy(), worker?.terminate()]);
  }
}

fileInput.addEventListener("change", async () => {
  const file = fileInput.files[0];
  if (!file) return;
  if (file.size > 10_000_000) {
    uploadStatus.textContent = "Choose a file under 10 MB.";
    return;
  }
  fileInput.disabled = submit.disabled = true;
  document.querySelector("#fill-guide").disabled = true;
  uploadStatus.textContent = "Reading your guide…";
  try {
    const data = file.name.toLowerCase().endsWith(".pdf")
      ? await readPdf(file)
      : { text: await recognize(file), limited: false };
    if (!data.text.trim()) throw new Error("No readable text found. Paste the key details below.");
    textInput.value = data.text.trim().slice(0, 4800);
    const limited = data.limited || data.text.trim().length > 4800;
    uploadStatus.textContent = limited
      ? "Part of the guide was extracted. Add any missing dates, gates, and sessions before planning."
      : "Text extracted. Check gate hours, access notes, and session times before planning.";
  } catch (error) {
    uploadStatus.textContent = `Could not read this guide. Paste its text or try a clearer file. ${error.message}`;
  } finally {
    fileInput.disabled = submit.disabled = false;
    document.querySelector("#fill-guide").disabled = false;
  }
});

function add(parent, tag, text) {
  const node = document.createElement(tag);
  node.textContent = text;
  parent.append(node);
  return node;
}

function list(title, items, format, empty) {
  const section = add(output, "section", "");
  section.className = "route";
  add(section, "h3", title);
  if (!items.length) {
    add(section, "p", empty);
    return;
  }
  const entries = add(section, "ul", "");
  for (const item of items) add(entries, "li", format(item));
}

function directions(label, origin, destination) {
  const query = new URLSearchParams({ api: "1", origin, destination });
  const link = add(output, "a", label);
  link.href = "https://www.google.com/maps/dir/?" + query;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
}

function render(plan) {
  add(output, "h2", plan.venue || "Your visit plan");
  add(output, "p", `${plan.context.arrival}–${plan.context.leave} · venue local time`);
  const { origin, destination } = plan.context;
  const entry = plan.targets.entry;
  const exit = plan.targets.exit;
  if (origin && (entry || destination)) {
    directions(entry ? `Directions to ${entry.name}` : "Directions to the venue", origin, entry?.point || destination);
  }
  if (origin && (exit || destination)) {
    directions(exit ? `Directions from ${exit.name}` : "Directions back to your starting point", exit?.point || destination, origin);
  }
  if (plan.traffic.status === "current") {
    add(output, "p", `Current TomTom driving estimates · ${plan.traffic.inbound.minutes} min in (${plan.traffic.inbound.delay} min delay), ${plan.traffic.outbound.minutes} min back (${plan.traffic.outbound.delay} min delay).`);
    if (plan.leave_base_if_current) {
      add(output, "p", `If current conditions hold, leave around ${plan.leave_base_if_current}. Allow extra time for parking and walking to the gate.`);
    }
  } else {
    add(output, "p", plan.traffic.reason);
  }
  const gate = (item) => `${item.name} · ${item.status}. Guide: ${item.source}`;
  for (const [key, title] of [["entry", "Entrance options"], ["exit", "Exit options"]]) {
    list(title, plan[key], gate, "The guide has no recognized gate information.");
    if (!plan[key].some((item) => item.status === "Eligible")) {
      add(output, "p", `Ask the organizer which ${key} is open at that time and whether it meets your access needs.`);
    }
  }
  list("Sessions during your visit", plan.sessions, (item) =>
    `${item.start}–${item.end} · ${item.name} · ${item.fit === "full" ? "Full session fits" : "Partial attendance only"}${item.overlaps ? " · overlaps another session" : ""}`,
    "No recognized session overlaps this visit.");
  if (plan.notes.length) list("Unclassified guide lines", plan.notes, (line) => line, "");
  const trace = add(output, "details", "");
  add(trace, "summary", "How the agents built this plan");
  const calls = add(trace, "ol", "");
  for (const action of plan.trace) {
    add(calls, "li", `${action.agent} · ${action.tool} (${action.mode}) · ${action.observation}`);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submit.disabled = true;
  output.replaceChildren();
  status.textContent = "Building your visit plan…";
  const value = (id) => document.getElementById(id).value;
  try {
    const response = await fetch("/api/scout/visit", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ guide: textInput.value, arrival: value("visit-arrival"),
        leave: value("visit-leave"), origin: value("origin"), destination: value("destination"),
        step_free: document.querySelector("#visit-access").checked }),
    });
    const plan = await response.json();
    if (!response.ok) throw new Error(plan.error || "Could not build a visit plan.");
    render(plan);
    status.textContent = "Visit plan ready.";
  } catch (error) {
    status.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});
