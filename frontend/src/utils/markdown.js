/** Render a minimal safe subset of Markdown (bold, inline code, lists, paragraphs). */
export function renderMarkdown(text) {
  const esc = t => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const inline = t => esc(t)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
  const out = [];
  let list = null;
  const close = () => {
    if (list) {
      out.push(`</${list}>`);
      list = null;
    }
  };
  for (const line of text.split("\n")) {
    const ul = line.match(/^\s*[-*]\s+(.*)/);
    const ol = line.match(/^\s*\d+[.)]\s+(.*)/);
    if (ul || ol) {
      const tag = ul ? "ul" : "ol";
      if (list !== tag) {
        close();
        out.push(`<${tag}>`);
        list = tag;
      }
      out.push(`<li>${inline((ul || ol)[1])}</li>`);
    } else {
      close();
      if (line.trim()) out.push(`<p>${inline(line)}</p>`);
    }
  }
  close();
  return out.join("");
}

