/**
 * AML Graph Copilot Client-Side Controller.
 */
document.addEventListener("DOMContentLoaded", () => {
  const chatMessages = document.getElementById("chat-messages");
  const chatInput = document.getElementById("chat-input");
  const chatSubmit = document.getElementById("chat-submit");
  const chipsPanel = document.getElementById("prompt-chips");
  const copilotStatus = document.getElementById("copilot-status");

  function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function formatMarkdown(text) {
    if (!text) return "";
    let html = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Format headers
    html = html.replace(/^### (.*$)/gim, "<h4>$1</h4>");
    html = html.replace(/^## (.*$)/gim, "<h3>$1</h3>");
    html = html.replace(/^# (.*$)/gim, "<h2>$1</h2>");

    // Format bold and italics
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*(.*?)\*/g, "<em>$1</em>");

    // Format inline code
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

    // Format list items
    html = html.replace(/^\- (.*$)/gim, "<li>$1</li>");
    html = html.replace(/(<li>.*<\/li>)/gim, "<ul>$1</ul>");
    // Clean nested ul tags
    html = html.replace(/<\/ul>\s*<ul>/g, "");

    // Format linebreaks
    html = html.replace(/\n\n/g, "<br><br>");
    html = html.replace(/\n/g, "<br>");

    return html;
  }

  function appendUserMessage(text) {
    const msgDiv = document.createElement("div");
    msgDiv.className = "msg msg-user";
    msgDiv.innerHTML = `
      <div class="msg-meta">👤 Аналитик</div>
      <div>${text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>
    `;
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
  }

  function appendAssistantMessage(text, toolName = null) {
    const msgDiv = document.createElement("div");
    msgDiv.className = "msg msg-assistant";

    let toolBadgeHtml = "";
    if (toolName) {
      toolBadgeHtml = `<div class="tool-badge">⚙️ Вызов инструмента: ${toolName}</div>`;
    }

    msgDiv.innerHTML = `
      <div class="msg-meta">🤖 AML Graph Copilot · Комплаенс-офицер</div>
      ${toolBadgeHtml}
      <div>${formatMarkdown(text)}</div>
    `;
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
  }

  function showTypingIndicator() {
    const ind = document.createElement("div");
    ind.id = "typing-indicator";
    ind.className = "typing-indicator";
    ind.innerHTML = `⏳ Анализирую связи графа и вызываю инструменты...`;
    chatMessages.appendChild(ind);
    scrollToBottom();
  }

  function hideTypingIndicator() {
    const ind = document.getElementById("typing-indicator");
    if (ind) ind.remove();
  }

  async function handleSendQuery(query) {
    const text = (query || chatInput.value || "").trim();
    if (!text) return;

    appendUserMessage(text);
    chatInput.value = "";
    chatSubmit.disabled = true;
    showTypingIndicator();

    try {
      const response = await fetch("/api/copilot/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text }),
      });

      hideTypingIndicator();

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        appendAssistantMessage(
          `⚠️ Ошибка сервера (${response.status}): ${errorData.detail || "Не удалось получить ответ"}`
        );
        return;
      }

      const data = await response.json();
      let toolName = null;
      if (text.toLowerCase().includes("общ") || text.toLowerCase().includes("аккумулир") || text.toLowerCase().includes("казначе")) {
        toolName = "find_common_recipients";
      } else if (text.toLowerCase().includes("сообществ") || text.toLowerCase().includes("кластер")) {
        toolName = "get_cluster_summary";
      } else if (/\d{10,19}/.test(text)) {
        toolName = "get_node_info";
      }

      appendAssistantMessage(data.answer, toolName);
    } catch (err) {
      hideTypingIndicator();
      appendAssistantMessage(
        `⚠️ Сбой сетевого соединения: ${err.message}. Проверьте доступность API.`
      );
    } finally {
      chatSubmit.disabled = false;
      chatInput.focus();
    }
  }

  chatSubmit.addEventListener("click", () => handleSendQuery());
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendQuery();
    }
  });

  if (chipsPanel) {
    chipsPanel.addEventListener("click", (e) => {
      const chip = e.target.closest(".chip");
      if (chip && chip.dataset.query) {
        handleSendQuery(chip.dataset.query);
      }
    });
  }

  // Auto-run if gid or q is provided in URL
  const urlParams = new URLSearchParams(window.location.search);
  const paramGid = urlParams.get("gid");
  const paramQ = urlParams.get("q");
  if (paramQ) {
    handleSendQuery(paramQ);
  } else if (paramGid) {
    handleSendQuery(`Каков финансовый профиль узла ${paramGid}?`);
  }
});
