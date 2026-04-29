const helloBtn = document.getElementById("helloBtn");
const output = document.getElementById("output");

helloBtn?.addEventListener("click", () => {
  if (!output) return;
  output.textContent = "🚀 Projeto app_exemplo_atena (Dashboard) pronto para evoluir!";
});
