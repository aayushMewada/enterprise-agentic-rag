const state = {
  chatHistory: [],
  documents: [],
  capabilities: {
    query_only: false,
    document_management: true,
  },
};

const els = {
  status: document.querySelector("#status"),
  yearFilter: document.querySelector("#yearFilter"),
  companyFilter: document.querySelector("#companyFilter"),
  messages: document.querySelector("#messages"),
  queryForm: document.querySelector("#queryForm"),
  question: document.querySelector("#question"),
  askButton: document.querySelector("#askButton"),
  clearChat: document.querySelector("#clearChat"),
  debugMode: document.querySelector("#debugMode"),
  docList: document.querySelector("#docList"),
  chatView: document.querySelector("#chatView"),
  docsView: document.querySelector("#docsView"),
  chatTab: document.querySelector("#chatTab"),
  docsTab: document.querySelector("#docsTab"),
  refreshDocs: document.querySelector("#refreshDocs"),
  uploadForm: document.querySelector("#uploadForm"),
  uploadButton: document.querySelector("#uploadButton"),
  ingestChanged: document.querySelector("#ingestChanged"),
  removeAllIndex: document.querySelector("#removeAllIndex"),
  activeFilters: document.querySelector("#activeFilters"),
};

boot();

async function boot() {
  wireUi();
  await checkHealth();
  await loadCapabilities();
  await Promise.all([loadMetadata(), loadDocuments()]);
}

function wireUi() {
  els.chatTab.addEventListener("click", () => setDocsVisible(false));
  els.docsTab.addEventListener("click", () => setDocsVisible(true));

  els.clearChat.addEventListener("click", () => {
    state.chatHistory = [];
    els.messages.innerHTML = "";
    updateStatus("Chat cleared");
  });

  els.refreshDocs.addEventListener("click", async () => {
    await Promise.all([loadMetadata(), loadDocuments()]);
    updateStatus("Documents refreshed");
  });

  els.question.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      els.queryForm.requestSubmit();
    }
  });
  els.yearFilter.addEventListener("change", updateActiveFilters);
  els.companyFilter.addEventListener("change", updateActiveFilters);
}

function setDocsVisible(visible) {
  els.chatView.classList.toggle("active", !visible);
  els.docsView.classList.toggle("active", visible);
  els.chatTab.classList.toggle("active", !visible);
  els.docsTab.classList.toggle("active", visible);
  els.clearChat.hidden = visible;
}

async function checkHealth() {
  try {
    const result = await apiGet("/health");
    updateStatus(result.ok ? "Backend connected" : "Backend unavailable");
  } catch (error) {
    updateStatus("Backend unavailable");
  }
}

async function loadCapabilities() {
  try {
    state.capabilities = await apiGet("/capabilities");
  } catch (error) {
    state.capabilities = {
      query_only: false,
      document_management: true,
    };
  }
  applyCapabilities();
}

function applyCapabilities() {
  const canManageDocuments = state.capabilities.document_management;
  els.uploadForm.hidden = !canManageDocuments;
  els.ingestChanged.hidden = !canManageDocuments;
  els.removeAllIndex.hidden = !canManageDocuments;
}

async function loadMetadata() {
  const metadata = await apiGet("/metadata");
  fillSelect(els.yearFilter, ["", ...metadata.years], "All years");
  fillSelect(els.companyFilter, ["", ...metadata.companies], "All companies");
  updateActiveFilters();
}

async function loadDocuments() {
  const result = await apiGet("/documents");
  state.documents = result.documents;
  renderDocuments();
}

function fillSelect(select, values, emptyLabel) {
  const current = select.value;
  select.innerHTML = "";
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value || emptyLabel;
    select.appendChild(option);
  }
  select.value = values.includes(current) ? current : "";
}

els.queryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = els.question.value.trim();
  if (!question) return;

  addUserMessage(question);
  const historyForRequest = [...state.chatHistory];
  state.chatHistory.push({ role: "user", content: question });
  els.question.value = "";
  setBusy(els.askButton, true, "Streaming...");

  const assistant = createAssistantMessage();

  try {
    const result = await streamQuery(
      {
        question,
        year: els.yearFilter.value || null,
        company: els.companyFilter.value || null,
        chat_history: historyForRequest,
        include_prompt: false,
      },
      assistant
    );

    state.chatHistory.push({ role: "assistant", content: result.answer });
  } catch (error) {
    assistant.setError(error.message);
  } finally {
    setBusy(els.askButton, false, "Ask");
    updateStatus("Backend connected");
  }
});

els.uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(els.uploadForm);
  setBusy(els.uploadButton, true, "Indexing...");

  try {
    await apiUpload("/documents/upload", formData);
    els.uploadForm.reset();
    await Promise.all([loadMetadata(), loadDocuments()]);
    updateStatus("Document uploaded and indexed");
  } catch (error) {
    addErrorMessage(error.message);
  } finally {
    setBusy(els.uploadButton, false, "Upload and index");
  }
});

els.ingestChanged.addEventListener("click", async () => {
  setBusy(els.ingestChanged, true, "Indexing...");
  try {
    const result = await apiPost("/documents/ingest", {});
    addAssistantNotice(
      `Index update complete.\nChanged/new files: ${result.changed_sources.length}\nDeleted files: ${result.deleted_sources.length}\nChunks added: ${result.chunks_added}`
    );
    await Promise.all([loadMetadata(), loadDocuments()]);
  } catch (error) {
    addErrorMessage(error.message);
  } finally {
    setBusy(els.ingestChanged, false, "Index changed files");
  }
});

els.removeAllIndex.addEventListener("click", async () => {
  const confirmed = window.confirm("Remove all chunks from the Qdrant index? Source PDFs will stay in data/raw.");
  if (!confirmed) return;

  setBusy(els.removeAllIndex, true, "Removing...");
  try {
    await apiDelete("/documents/all", { delete_files: false });
    addAssistantNotice("All indexed chunks were removed. Source files were kept.");
  } catch (error) {
    addErrorMessage(error.message);
  } finally {
    setBusy(els.removeAllIndex, false, "Remove all from index");
  }
});

async function streamQuery(payload, assistant) {
  const response = await fetch("/query/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Request failed with ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      if (event.type === "status") {
        assistant.setStatus(event.message);
        updateStatus(event.message);
      } else if (event.type === "sources") {
        assistant.setSources(event.sources || []);
        if (els.debugMode.checked) {
          assistant.setChunks(event.chunks || []);
        }
      } else if (event.type === "token") {
        answer += event.token;
        assistant.setContent(answer);
      } else if (event.type === "replace") {
        answer = event.answer || "";
        assistant.setContent(answer);
      } else if (event.type === "error") {
        throw new Error(event.message);
      }
    }
  }

  assistant.setStatus("Answer");
  return { answer };
}

function addUserMessage(content) {
  const message = createMessage("user", "You");
  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = content;
  message.appendChild(body);
  els.messages.appendChild(message);
  scrollMessages();
}

function addAssistantNotice(content) {
  const message = createMessage("assistant", "System");
  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = content;
  message.appendChild(body);
  els.messages.appendChild(message);
  scrollMessages();
}

function addErrorMessage(content) {
  const message = createMessage("error", "Error");
  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = content;
  message.appendChild(body);
  els.messages.appendChild(message);
  scrollMessages();
}

function createAssistantMessage() {
  const message = createMessage("assistant", "Retrieving sources");
  const body = document.createElement("div");
  body.className = "message-body markdown";

  const citations = document.createElement("details");
  citations.className = "citations";
  citations.hidden = true;
  const citationSummary = document.createElement("summary");
  citationSummary.textContent = "Show citations";
  const sources = document.createElement("div");
  sources.className = "sources";
  citations.append(citationSummary, sources);

  const chunks = document.createElement("details");
  chunks.className = "chunks";
  chunks.hidden = true;
  const summary = document.createElement("summary");
  summary.textContent = "Retrieved chunks";
  chunks.appendChild(summary);

  message.append(body, citations, chunks);
  els.messages.appendChild(message);
  scrollMessages();

  return {
    setStatus(label) {
      message.querySelector(".message-meta").textContent = label;
    },
    setContent(content) {
      body.innerHTML = renderMarkdown(content);
      scrollMessages();
    },
    setSources(items) {
      sources.innerHTML = "";
      citations.hidden = !items.length;
      citationSummary.textContent = `Show citations (${items.length})`;
      for (const source of items) {
        sources.appendChild(renderSource(source));
      }
    },
    setChunks(items) {
      chunks.hidden = !items.length;
      chunks.querySelectorAll(".chunk-card").forEach((node) => node.remove());
      for (const chunk of items) {
        const card = document.createElement("div");
        card.className = "chunk-card";
        card.textContent = `[${chunk.source}, page ${chunk.page_start ?? "?"}] ${chunk.text}`;
        chunks.appendChild(card);
      }
    },
    setError(content) {
      message.className = "message error";
      message.querySelector(".message-meta").textContent = "Error";
      body.textContent = content;
    },
  };
}

function createMessage(role, label) {
  const message = document.createElement("article");
  message.className = `message ${role}`;

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = label;
  message.appendChild(meta);

  return message;
}

function renderSource(source) {
  const card = document.createElement("div");
  card.className = "source-card";

  if (source.source === "Document library metadata") {
    const title = document.createElement("div");
    title.className = "source-title";
    title.textContent = source.source;

    const meta = document.createElement("div");
    meta.className = "source-meta";
    meta.textContent = "Generated from the current document inventory";

    card.append(title, meta);
    return card;
  }

  const label = source.page ? `Page ${source.page}` : "Page unknown";
  const title = document.createElement("div");
  title.className = "source-title";
  title.textContent = source.source || "Unknown source";

  const meta = document.createElement("div");
  meta.className = "source-meta";
  meta.textContent = `${source.company || "Unknown company"} | ${source.year || "Unknown year"} | ${label}`;

  card.append(title, meta);
  return card;
}

function renderDocuments() {
  els.docList.innerHTML = "";

  if (!state.documents.length) {
    const empty = document.createElement("div");
    empty.className = "doc-card";
    empty.textContent = "No source documents found.";
    els.docList.appendChild(empty);
    return;
  }

  for (const doc of state.documents) {
    const card = document.createElement("div");
    card.className = "doc-card";

    const title = document.createElement("div");
    title.className = "doc-title";
    title.textContent = doc.source;

    const meta = document.createElement("div");
    meta.className = "doc-meta";
    meta.textContent = `${doc.company || "Unknown company"} | ${doc.year || "Unknown year"} | ${formatBytes(doc.size)}`;

    const remove = document.createElement("button");
    remove.className = "danger-button";
    remove.type = "button";
    remove.textContent = "Delete file and chunks";
    remove.hidden = !state.capabilities.document_management;
    remove.addEventListener("click", async () => {
      const confirmed = window.confirm(`Delete ${doc.source} from disk and index?`);
      if (!confirmed) return;
      await apiDelete("/documents", { source: doc.source, delete_file: true });
      await Promise.all([loadMetadata(), loadDocuments()]);
    });

    card.append(title, meta);
    if (state.capabilities.document_management) {
      card.appendChild(remove);
    }
    els.docList.appendChild(card);
  }
}

async function apiGet(path) {
  const response = await fetch(path);
  return parseResponse(response);
}

async function apiPost(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}

async function apiDelete(path, payload) {
  const response = await fetch(path, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}

async function apiUpload(path, formData) {
  const response = await fetch(path, {
    method: "POST",
    body: formData,
  });
  return parseResponse(response);
}

async function parseResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `Request failed with ${response.status}`);
  }
  return data;
}

function renderMarkdown(text) {
  const normalized = normalizeMarkdown(text);

  if (window.marked && window.DOMPurify) {
    window.marked.setOptions({
      breaks: true,
      gfm: true,
    });
    return window.DOMPurify.sanitize(window.marked.parse(normalized));
  }

  return escapeHtml(normalized).replace(/\n/g, "<br>");
}

function normalizeMarkdown(text) {
  return text
    .replace(/[ \t]*\\[ \t]*\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function setBusy(button, busy, label) {
  button.disabled = busy;
  button.textContent = label;
}

function updateStatus(message) {
  els.status.textContent = message;
}

function updateActiveFilters() {
  const year = els.yearFilter.value || "all years";
  const company = els.companyFilter.value || "all companies";
  els.activeFilters.textContent = `Filters: ${year}, ${company}`;
}

function scrollMessages() {
  els.messages.scrollTop = els.messages.scrollHeight;
}

function formatBytes(bytes) {
  if (typeof bytes !== "number") return "Indexed in Qdrant";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
