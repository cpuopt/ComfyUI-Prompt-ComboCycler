import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const SOURCE_TYPE = "PROMPT_MATRIX_SOURCE";
const SOURCE_NODE = "PromptMatrixSource";
const CONTROLLER_NODE = "PromptMatrixController";

function getWidget(node, name) {
  return node.widgets?.find((widget) => widget.name === name);
}

function parseLines(text) {
  return String(text ?? "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function factorialRatio(n, k) {
  let result = 1n;
  for (let value = BigInt(n - k + 1); value <= BigInt(n); value += 1n) {
    result *= value;
  }
  return result;
}

function combinationCount(n, k) {
  if (k < 0 || k > n) return 0n;
  const kk = Math.min(k, n - k);
  let result = 1n;
  for (let i = 1; i <= kk; i += 1) {
    result = (result * BigInt(n - kk + i)) / BigInt(i);
  }
  return result;
}

function formatBigInt(value) {
  const raw = value.toString();
  if (raw.length <= 12) return raw;
  return `${raw.slice(0, 6)}e+${raw.length - 1}`;
}

function sourceCount(node) {
  const enabled = getWidget(node, "enabled")?.value ?? true;
  if (!enabled) return 1n;
  const text = getWidget(node, "text")?.value ?? "";
  const n = parseLines(text).length;
  if (n === 0) return 1n;
  const chooseWidget = getWidget(node, "choose_k");
  const k = Math.max(1, Math.min(Number(chooseWidget?.value ?? 1), n));
  const mode = getWidget(node, "mode")?.value ?? "combination";
  return mode === "permutation" ? factorialRatio(n, k) : combinationCount(n, k);
}

function updateSourceTitle(node, status) {
  const countText = status ?? `${formatBigInt(sourceCount(node))} possible`;
  node.title = `Prompt Matrix Source (${countText})`;
}

function updateControllerTitle(node, status) {
  node.title = status ? `Prompt Matrix Controller (${status})` : "Prompt Matrix Controller";
}

function wrapWidgetCallbacks(node, callback) {
  for (const widget of node.widgets ?? []) {
    if (widget.__promptMatrixWrapped) continue;
    const previous = widget.callback;
    widget.callback = function (...args) {
      const result = previous?.apply(this, args);
      callback();
      return result;
    };
    widget.__promptMatrixWrapped = true;
  }
}

function nextSourceInputName(node) {
  const used = new Set((node.inputs ?? []).map((input) => input.name));
  let index = 1;
  while (used.has(`source_${index}`)) index += 1;
  return `source_${index}`;
}

function addSourceInput(node) {
  node.addInput(nextSourceInputName(node), SOURCE_TYPE);
  node.setDirtyCanvas(true, true);
}

function removeLastSourceInput(node) {
  const inputs = node.inputs ?? [];
  for (let index = inputs.length - 1; index >= 0; index -= 1) {
    if (inputs[index].type === SOURCE_TYPE || inputs[index].name?.startsWith("source_")) {
      node.removeInput(index);
      node.setDirtyCanvas(true, true);
      return;
    }
  }
}

async function resetCursor(node) {
  await api.fetchApi("/prompt_matrix/reset_cursor", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ node_id: String(node.id) }),
  });
  updateControllerTitle(node, "reset");
  node.setDirtyCanvas(true, true);
}

app.registerExtension({
  name: "ComfyUI.PromptMatrix",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name === SOURCE_NODE) {
      const onNodeCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function (...args) {
        const result = onNodeCreated?.apply(this, args);
        updateSourceTitle(this);
        wrapWidgetCallbacks(this, () => updateSourceTitle(this));
        return result;
      };

      const onExecuted = nodeType.prototype.onExecuted;
      nodeType.prototype.onExecuted = function (message, ...args) {
        const result = onExecuted?.apply(this, [message, ...args]);
        updateSourceTitle(this, message?.status?.[0]);
        return result;
      };
    }

    if (nodeData.name === CONTROLLER_NODE) {
      const onNodeCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function (...args) {
        const result = onNodeCreated?.apply(this, args);
        this.addWidget("button", "Add Source Input", null, () => addSourceInput(this));
        this.addWidget("button", "Remove Source Input", null, () => removeLastSourceInput(this));
        this.addWidget("button", "Reset Cursor", null, () => resetCursor(this));
        updateControllerTitle(this);
        return result;
      };

      const onExecuted = nodeType.prototype.onExecuted;
      nodeType.prototype.onExecuted = function (message, ...args) {
        const result = onExecuted?.apply(this, [message, ...args]);
        updateControllerTitle(this, message?.status?.[0]);
        return result;
      };
    }
  },
});
