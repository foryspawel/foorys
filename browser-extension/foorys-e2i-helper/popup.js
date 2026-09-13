const input = document.querySelector("#decoder");
const status = document.querySelector("#status");

chrome.storage.local.get("decoderAddress").then(({ decoderAddress }) => {
  input.value = decoderAddress || "192.168.18.177:9001";
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
