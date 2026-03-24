(function () {
  "use strict";

  function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      var cookies = document.cookie.split(";");
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + "=") {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  function escapeHtml(raw) {
    var div = document.createElement("div");
    div.textContent = raw || "";
    return div.innerHTML;
  }

  function renderInlineMarkdown(raw) {
    var text = escapeHtml(raw || "");
    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, function (_, label, url) {
      return '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + label + "</a>";
    });
    text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
    text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/__([^_]+)__/g, "<strong>$1</strong>");
    text = text.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    text = text.replace(/_([^_]+)_/g, "<em>$1</em>");
    text = text.replace(/~~([^~]+)~~/g, "<del>$1</del>");
    return text;
  }

  function renderMarkdown(raw) {
    var source = String(raw || "").replace(/\r\n/g, "\n");
    var codeBlocks = [];

    source = source.replace(/```([a-zA-Z0-9_-]+)?\n([\s\S]*?)```/g, function (_, lang, code) {
      var idx = codeBlocks.length;
      codeBlocks.push({
        lang: lang || "",
        code: escapeHtml(code || "")
      });
      return "@@CODEBLOCK_" + idx + "@@";
    });

    var lines = source.split("\n");
    var html = "";
    var listMode = null;

    function closeList() {
      if (listMode) {
        html += "</" + listMode + ">";
        listMode = null;
      }
    }

    lines.forEach(function (line) {
      var trimmed = line.trim();

      if (/^@@CODEBLOCK_\d+@@$/.test(trimmed)) {
        closeList();
        html += "<p>" + trimmed + "</p>";
        return;
      }

      var headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
      if (headingMatch) {
        closeList();
        var level = headingMatch[1].length;
        html += "<h" + level + ">" + renderInlineMarkdown(headingMatch[2]) + "</h" + level + ">";
        return;
      }

      var ulMatch = trimmed.match(/^[-*]\s+(.+)$/);
      if (ulMatch) {
        if (listMode !== "ul") {
          closeList();
          listMode = "ul";
          html += "<ul>";
        }
        html += "<li>" + renderInlineMarkdown(ulMatch[1]) + "</li>";
        return;
      }

      var olMatch = trimmed.match(/^\d+\.\s+(.+)$/);
      if (olMatch) {
        if (listMode !== "ol") {
          closeList();
          listMode = "ol";
          html += "<ol>";
        }
        html += "<li>" + renderInlineMarkdown(olMatch[1]) + "</li>";
        return;
      }

      if (!trimmed) {
        closeList();
        html += "<br>";
        return;
      }

      closeList();
      html += "<p>" + renderInlineMarkdown(trimmed) + "</p>";
    });

    closeList();

    html = html.replace(/@@CODEBLOCK_(\d+)@@/g, function (_, idx) {
      var block = codeBlocks[parseInt(idx, 10)];
      if (!block) return "";
      var lang = block.lang ? '<span class="cm-ai-code-lang">' + escapeHtml(block.lang) + "</span>" : "";
      return '<pre><code>' + block.code + "</code>" + lang + "</pre>";
    });

    return html;
  }

  function autoGrow(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }

  function fileToBase64(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () {
        var result = reader.result || "";
        var base64 = String(result).split(",")[1] || "";
        resolve({
          name: file.name,
          mime_type: file.type || "image/png",
          data_base64: base64
        });
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function createWidget() {
    var root = document.getElementById("cm-ai-chat-widget");
    if (!root) return;

    var endpoint = root.getAttribute("data-endpoint");
    var metaEndpoint = root.getAttribute("data-meta-endpoint");
    var maxImages = parseInt(root.getAttribute("data-max-images") || "3", 10);
    var toggleBtn = document.getElementById("cm-ai-chat-toggle");
    var panel = document.getElementById("cm-ai-chat-panel");
    var closeBtn = document.getElementById("cm-ai-chat-close");
    var messagesEl = document.getElementById("cm-ai-chat-messages");
    var inputEl = document.getElementById("cm-ai-chat-input");
    var sendBtn = document.getElementById("cm-ai-chat-send");
    var fileInput = document.getElementById("cm-ai-chat-image-input");
    var previewsEl = document.getElementById("cm-ai-chat-previews");
    var modelSelect = document.getElementById("cm-ai-chat-model-select");
    var mcpSelect = document.getElementById("cm-ai-chat-mcp-select");
    var newChatBtn = document.getElementById("cm-ai-chat-new");

    var pendingImages = [];
    var history = [];
    var loading = false;
    var requestTimeoutMs = 60000;
    var defaultModel = "";

    function looksLikeBusinessQuestion(text) {
      var raw = (text || "").toLowerCase();
      var words = ["cliente", "clientes", "venta", "ventas", "facturacion", "compras", "mejor cliente", "ingreso", "ticket"];
      return words.some(function (w) { return raw.indexOf(w) !== -1; });
    }

    function appendMessage(role, content, extraClass) {
      var div = document.createElement("div");
      div.className =
        "cm-ai-chat-msg " +
        (role === "user" ? "cm-ai-chat-msg--user" : "cm-ai-chat-msg--assistant") +
        (extraClass ? " " + extraClass : "");
      var isStatus = extraClass && extraClass.indexOf("cm-ai-chat-msg--status") >= 0;
      if (role === "assistant" && !isStatus) {
        div.innerHTML = renderMarkdown(content || "");
      } else {
        div.innerHTML = escapeHtml(content || "");
      }
      messagesEl.appendChild(div);
      messagesEl.scrollTop = messagesEl.scrollHeight;
      return div;
    }

    function setLoading(state) {
      loading = !!state;
      sendBtn.disabled = loading;
      if (loading) {
        root.classList.add("is-loading");
      } else {
        root.classList.remove("is-loading");
      }
    }

    function renderPreviews() {
      previewsEl.innerHTML = "";
      pendingImages.forEach(function (img, index) {
        var item = document.createElement("div");
        item.className = "cm-ai-chat-preview-item";
        item.innerHTML =
          '<i class="bi bi-image"></i><span>' +
          escapeHtml(img.name || "imagen") +
          "</span>";
        var remove = document.createElement("button");
        remove.type = "button";
        remove.className = "cm-ai-chat-preview-remove";
        remove.innerHTML = '<i class="bi bi-x-circle"></i>';
        remove.addEventListener("click", function () {
          pendingImages.splice(index, 1);
          renderPreviews();
        });
        item.appendChild(remove);
        previewsEl.appendChild(item);
      });
    }

    function resetChat() {
      history = [];
      pendingImages = [];
      renderPreviews();
      messagesEl.innerHTML = "";
      appendMessage("assistant", "Hola, soy tu asistente. ¿Qué necesitas revisar hoy?");
      if (defaultModel && modelSelect) {
        modelSelect.value = defaultModel;
      }
      if (mcpSelect) {
        mcpSelect.value = "auto";
      }
    }

    function setModelOptions(meta) {
      if (!modelSelect || !meta) return;
      var options = meta.options || [];
      defaultModel = meta.default_model || "";
      modelSelect.innerHTML = "";
      options.forEach(function (opt) {
        var optionEl = document.createElement("option");
        optionEl.value = opt.value;
        optionEl.textContent = opt.label || opt.value;
        modelSelect.appendChild(optionEl);
      });
      if (defaultModel) {
        modelSelect.value = defaultModel;
      }
    }

    async function loadMeta() {
      if (!metaEndpoint) return;
      try {
        var response = await fetch(metaEndpoint, { method: "GET" });
        var data = await response.json();
        if (response.ok && data.success) {
          setModelOptions(data);
        }
      } catch (e) {
        // noop
      }
    }

    async function onFilesSelected() {
      if (!fileInput.files || !fileInput.files.length) return;
      var files = Array.prototype.slice.call(fileInput.files);
      var remainSlots = Math.max(maxImages - pendingImages.length, 0);
      if (remainSlots <= 0) {
        appendMessage("assistant", "Ya alcanzaste el máximo de imágenes por mensaje.");
        fileInput.value = "";
        return;
      }
      files = files.slice(0, remainSlots);

      try {
        var encoded = await Promise.all(files.map(fileToBase64));
        pendingImages = pendingImages.concat(encoded).slice(0, maxImages);
        renderPreviews();
      } catch (e) {
        appendMessage("assistant", "No pude procesar una de las imágenes.");
      } finally {
        fileInput.value = "";
      }
    }

    async function sendMessage() {
      if (loading) return;
      var text = (inputEl.value || "").trim();
      if (!text && pendingImages.length === 0) return;

      appendMessage("user", text || "[Imagen adjunta]");
      history.push({ role: "user", content: text || "[Imagen adjunta]" });

      inputEl.value = "";
      autoGrow(inputEl);

      var forceMcp = mcpSelect && mcpSelect.value === "force";
      var useMcpHint = pendingImages.length === 0 && (forceMcp || looksLikeBusinessQuestion(text));
      var stages = useMcpHint
        ? ["Pensando...", "Consultando contexto del negocio...", "Usando MCP de solo lectura...", "Analizando resultados MCP...", "Redactando respuesta..."]
        : ["Pensando...", "Analizando tu mensaje...", "Redactando respuesta..."];
      var stageIndex = 0;
      var statusMsg = appendMessage("assistant", stages[stageIndex], "cm-ai-chat-msg--status");
      var stageTimer = setInterval(function () {
        stageIndex = (stageIndex + 1) % stages.length;
        statusMsg.textContent = stages[stageIndex];
      }, 1400);
      setLoading(true);

      try {
        var controller = new AbortController();
        var timeoutId = setTimeout(function () {
          controller.abort();
        }, requestTimeoutMs);

        var response = await fetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken") || ""
          },
          signal: controller.signal,
          body: JSON.stringify({
            message: text,
            images: pendingImages,
            history: history.slice(-4),
            model_override: modelSelect && modelSelect.value ? modelSelect.value : null,
            mcp_mode: mcpSelect && mcpSelect.value ? mcpSelect.value : "auto"
          })
        });
        clearTimeout(timeoutId);
        var rawBody = await response.text();
        var data = null;
        try {
          data = rawBody ? JSON.parse(rawBody) : null;
        } catch (parseError) {
          data = null;
        }
        clearInterval(stageTimer);
        statusMsg.remove();

        if ((response.redirected && /\/login\b/.test(response.url || "")) || (!data && /<html/i.test(rawBody || ""))) {
          appendMessage(
            "assistant",
            "Tu sesión parece expirada. Recarga la página e inicia sesión de nuevo."
          );
          return;
        }

        if (!data) {
          appendMessage(
            "assistant",
            "El servidor devolvió una respuesta no válida. Intenta de nuevo en unos segundos."
          );
          return;
        }

        if (!response.ok || !data.success) {
          var extra = data && data.details ? "\n\n" + data.details : "";
          appendMessage(
            "assistant",
            ((data && data.error) || "No se pudo procesar tu consulta en este momento.") + extra
          );
          return;
        }
        appendMessage("assistant", data.answer || "Sin respuesta.");
        if (data && data.mcp_used) {
          appendMessage("assistant", "Acción: usé MCP de base de datos (solo lectura) para responder.", "cm-ai-chat-msg--status");
        } else if (data && data.mcp_mode === "force") {
          appendMessage("assistant", "Aviso: forzaste MCP pero no se logró usar contexto DB.", "cm-ai-chat-msg--status");
        }
        history.push({ role: "assistant", content: data.answer || "" });
      } catch (error) {
        clearInterval(stageTimer);
        statusMsg.remove();
        if (error && error.name === "AbortError") {
          appendMessage(
            "assistant",
            "La respuesta tardó demasiado. Intenta una pregunta más corta o cambia a un modelo más rápido."
          );
        } else {
          var networkDetail = error && error.message ? (" Detalle técnico: " + error.message) : "";
          appendMessage("assistant", "Error de conexión con el asistente." + networkDetail);
        }
      } finally {
        pendingImages = [];
        renderPreviews();
        setLoading(false);
      }
    }

    function openPanel() {
      root.classList.add("is-open");
      setTimeout(function () {
        inputEl.focus();
      }, 60);
    }

    function closePanel() {
      root.classList.remove("is-open");
    }

    toggleBtn.addEventListener("click", function () {
      if (root.classList.contains("is-open")) {
        closePanel();
      } else {
        openPanel();
      }
    });
    closeBtn.addEventListener("click", closePanel);
    fileInput.addEventListener("change", onFilesSelected);
    sendBtn.addEventListener("click", sendMessage);
    newChatBtn.addEventListener("click", resetChat);
    inputEl.addEventListener("input", function () {
      autoGrow(inputEl);
    });
    inputEl.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    loadMeta();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", createWidget);
  } else {
    createWidget();
  }
})();
