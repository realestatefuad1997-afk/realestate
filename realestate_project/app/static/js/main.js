console.log("RealEstate project loaded");

async function shareOrCopy(url, title) {
  try {
    if (navigator.share) {
      await navigator.share({ title: title || document.title, url });
      return true;
    }
  } catch (err) {
    // If user cancels or share fails, fallback to copy
  }
  try {
    await navigator.clipboard.writeText(url);
    alert("تم نسخ رابط المشاركة إلى الحافظة");
    return true;
  } catch (err) {
    // Last resort: prompt
    const ok = window.prompt("انسخ الرابط:", url);
    return !!ok;
  }
}

document.addEventListener("click", function (e) {
  const btn = e.target.closest("#share-button, .share-btn");
  if (!btn) return;
  const url = btn.getAttribute("data-share-url") || window.location.href;
  const title = btn.getAttribute("data-share-title") || document.title;
  shareOrCopy(url, title);
});