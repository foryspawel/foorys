const input = document.querySelector("#decoder");
const relayInput = document.querySelector("#relay");
const captureInput = document.querySelector("#capture-code");
const status = document.querySelector("#status");

chrome.storage.local.get(["decoderAddress", "relayUrl", "relayCaptureCode"]).then(({ decoderAddress, relayUrl, relayCaptureCode }) => {
  input.value = decoderAddress || "192.168.18.177:9001";
  relayInput.value = relayUrl || "https://raport.forys.pro:9443";
  captureInput.value = relayCaptureCode || "";
});

document.querySelector("#save").addEventListener("click", async () => {
  const address = input.value.trim().replace(/^https?:\/\//, "").replace(/\/$/, "");
  if (!/^[A-Za-z0-9.:-]+$/.test(address)) {
    status.textContent = "Wpisz sam adres, np. 192.168.18.177:9001.";
    return;
  }
  await chrome.storage.local.set({ decoderAddress: address });
  status.textContent = "Adres zapisany.";
});

document.querySelector("#open").addEventListener("click", async () => {
  const address = input.value.trim().replace(/^https?:\/\//, "").replace(/\/$/, "");
  if (!/^[A-Za-z0-9.:-]+$/.test(address)) {
    status.textContent = "Najpierw wpisz prawidłowy adres dekodera.";
    return;
  }
  await chrome.storage.local.set({ decoderAddress: address });
  await chrome.tabs.create({ url: "http://" + address + "/" });
  window.close();
});

document.querySelector("#activate").addEventListener("click", async () => {
  const relayUrl = relayInput.value.trim().replace(/\/$/, "");
  const captureCode = captureInput.value.trim();
  let parsed;
  try { parsed = new URL(relayUrl); } catch (_error) { parsed = null; }
  if (!parsed || (parsed.protocol !== "https:" && parsed.protocol !== "http:")) {
    status.textContent = "Wpisz adres Relay z HTTPS.";
    return;
  }
  if (!/^\d{6}$/.test(captureCode)) {
    status.textContent = "Kod przechwycenia musi mieć 6 cyfr.";
    return;
  }
  await chrome.storage.local.set({ relayUrl, relayCaptureCode: captureCode });
  status.textContent = "Przechwycenie aktywne. Teraz otwórz adres QR i potwierdź CAPTCHA.";
});

document.querySelector("#clear").addEventListener("click", async () => {
  await chrome.storage.local.remove("relayCaptureCode");
  captureInput.value = "";
  status.textContent = "Kod przechwycenia wyczyszczony.";
});
