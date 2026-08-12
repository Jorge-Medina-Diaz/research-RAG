// Valida cada bloque ```mermaid de los .md indicados.
import { readFileSync, readdirSync } from "node:fs";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  pretendToBeVisual: true,
});
globalThis.window = dom.window;
globalThis.document = dom.window.document;
// navigator es un getter en Node 22: hay que definirlo, no asignarlo.
Object.defineProperty(globalThis, "navigator", {
  value: dom.window.navigator,
  configurable: true,
});
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.SVGElement = dom.window.SVGElement;
globalThis.DOMPurify = { sanitize: (s) => s, addHook: () => {} };

const mermaid = (await import("mermaid")).default;
mermaid.initialize({ startOnLoad: false, securityLevel: "loose" });

const raiz = process.argv[2];
const ficheros = [
  `${raiz}/README.md`,
  ...readdirSync(`${raiz}/docs`).map((f) => `${raiz}/docs/${f}`),
].filter((f) => f.endsWith(".md"));

let total = 0;
let malos = 0;

for (const f of ficheros) {
  // Normalizar CRLF: en un checkout de Windows los ficheros que git ha tocado
  // llevan \r\n, y el regex de abajo busca \n. Sin esto el validador saltaba
  // ficheros enteros en silencio — daba «11/11 válidos» habiendo 26 diagramas,
  // que es peor que fallar: un detector mudo se lee como un aprobado.
  const texto = readFileSync(f, "utf8").replace(/\r\n/g, "\n");
  const bloques = [...texto.matchAll(/```mermaid\n([\s\S]*?)```/g)];
  for (const [i, m] of bloques.entries()) {
    total++;
    const codigo = m[1];
    const linea = texto.slice(0, m.index).split("\n").length;
    try {
      await mermaid.parse(codigo);
    } catch (e) {
      malos++;
      const tipo = codigo.trim().split("\n")[0].slice(0, 40);
      console.log(`\nFALLA  ${f}:${linea}  (diagrama ${i + 1}, ${tipo})`);
      console.log(
        "  " + String(e.message || e).split("\n").slice(0, 6).join("\n  "),
      );
    }
  }
}
console.log(`\n${total - malos}/${total} diagramas válidos`);
process.exit(malos ? 1 : 0);
