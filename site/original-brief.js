"use strict";

function originalBrief(project) {
  const description = project.originalDescription;
  const panel = document.createElement("details");
  panel.className = "original-brief";
  const heading = document.createElement("summary");
  const english = description?.language?.toLowerCase().split("-")[0] === "en";
  heading.textContent = english ? "Описание клиента на английском" :
    description?.translationEn ? "Оригинал клиента и перевод на английский" : "Оригинал описания клиента";
  panel.append(heading);

  if (description?.text) {
    const label = document.createElement("small");
    const date = new Date(description.retrievedAt).toLocaleDateString("ru-RU", {timeZone: "Europe/Kyiv"});
    label.textContent = (description.quality === "full" ? "Полный текст" : "Фрагмент из поиска") + " · Upwork · " + date;
    panel.append(label);
    const body = document.createElement("div");
    body.className = "original-brief-text";
    body.dir = "auto";
    if (description.language) body.lang = description.language;
    body.textContent = description.text;
    panel.append(body);
    if (description.translationEn) {
      const caption = document.createElement("h4");
      caption.textContent = "Перевод на английский";
      const translation = document.createElement("div");
      translation.className = "original-brief-text";
      translation.lang = "en";
      translation.textContent = description.translationEn;
      panel.append(caption, translation);
    }
  }
  if (description?.quality !== "full") {
    const link = document.createElement("a");
    link.href = project.url;
    link.textContent = "Посмотреть описание на Upwork ↗";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    panel.append(link);
  }
  return panel;
}
