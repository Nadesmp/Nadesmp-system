// Add the official Discord invite URL here when it is available.
const DISCORD_INVITE_URL = "";
const discordLink = document.getElementById("discord-link");
document.getElementById("year").textContent = new Date().getFullYear();
if (DISCORD_INVITE_URL) {
  discordLink.href = DISCORD_INVITE_URL;
  discordLink.textContent = "Join the Discord ↗";
  discordLink.target = "_blank";
  discordLink.rel = "noopener noreferrer";
} else {
  discordLink.addEventListener("click", (event) => {
    event.preventDefault();
    alert("The official Discord invite has not been configured yet.");
  });
}
