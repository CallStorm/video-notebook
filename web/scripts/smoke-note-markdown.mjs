import { Window } from "happy-dom";
const window = new Window({ url: "https://localhost/" });
const { document } = window;
globalThis.window = window;
globalThis.document = document;
globalThis.Node = window.Node;
globalThis.Element = window.Element;
globalThis.HTMLElement = window.HTMLElement;
globalThis.DocumentFragment = window.DocumentFragment;
try {
  globalThis.navigator = window.navigator;
} catch {
  Object.defineProperty(globalThis, "navigator", { value: window.navigator, configurable: true });
}
globalThis.getComputedStyle = window.getComputedStyle.bind(window);
globalThis.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);
globalThis.MutationObserver = window.MutationObserver;

const { Editor } = await import("@tiptap/core");
const StarterKit = (await import("@tiptap/starter-kit")).default;
const { TableKit } = await import("@tiptap/extension-table");
const { Markdown } = await import("tiptap-markdown");

const fixture = `# 需求清单

| 功能描述 | 优先级 | 状态 |
| --- | --- | --- |
| 用户登录 | P0 | 完成 |
| 笔记编辑 | P1 | 进行中 |

正文里还有 **粗体**、~~删除线~~ 和 \`code\`。

\`\`\`js
console.log(1)
\`\`\`

---

> 引用一行

- 列表 A
1. 有序 B
`;

const el = document.createElement("div");
document.body.appendChild(el);

const editor = new Editor({
  element: el,
  extensions: [
    StarterKit.configure({
      heading: { levels: [1, 2, 3] },
      link: { openOnClick: false },
    }),
    TableKit.configure({ table: { resizable: false } }),
    Markdown.configure({ html: false }),
  ],
  content: fixture,
});

const md = editor.storage.markdown.getMarkdown();
const json = editor.getJSON();
const hasTable = JSON.stringify(json).includes('"type":"table"');
console.log("HAS_TABLE_NODE=", hasTable);
console.log("---ROUNDTRIP---");
console.log(md);
console.log("---END---");

const okTable = hasTable && md.includes("|") && md.includes("功能描述") && md.includes("用户登录");
const okStrike = md.includes("~~") || md.includes("删除线");
const okCode = md.includes("```") || md.includes("console.log");
const okHr = md.includes("---") || md.includes("***") || md.includes("* * *");
const okQuote = md.includes(">");
console.log("PASS_TABLE=", okTable);
console.log("PASS_STRIKE=", okStrike);
console.log("PASS_CODE=", okCode);
console.log("PASS_HR=", okHr);
console.log("PASS_QUOTE=", okQuote);

editor.destroy();
window.close();
if (!okTable) process.exit(1);