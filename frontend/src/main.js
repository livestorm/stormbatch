import { createApp } from "vue";
import "./styles/livestorm-tokens/index.css";
import "./styles/livestorm.css";
import App from "./App.vue";

document.body.setAttribute("data-colors-primitive", "Livestorm");
document.body.setAttribute("data-colors-semantic", "dark");

createApp(App).mount("#app");
