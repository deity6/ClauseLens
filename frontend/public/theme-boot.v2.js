/* 首帧前的主题引导：在 CSS 与正文绘制之前决定 <html data-theme>，避免「先闪一下浅色再变深」。
 *
 * 为什么是一个外部小文件而不是 index.html 里的内联 <script>：
 * 线上 CSP 是 `script-src 'self'`（见 frontend/public/_headers），内联脚本会被浏览器直接拦掉——
 * 那样手机上的「跟随系统深色」就只能在 React 挂载后才生效，首帧仍是浅色。
 * 外链 self 脚本不破坏 CSP，也不需要给内联脚本维护 hash。
 *
 * 文件名带版本号：自定义域上 CF 的「浏览器缓存 TTL」会盖掉 _headers 里的 Cache-Control（实测 4h），
 * 所以逻辑一改就升 vN，并同步 index.html 的 <script src>，别指望固定路径立刻换新。
 *
 * 为什么不用 matchMedia("(max-width: 900px)") 判移动端：
 * 文档刚开始解析时，移动端的布局视口还是默认的 980px（viewport meta 还没落到布局上），
 * 这条查询会返回 false —— 实测 iPhone 模拟：innerWidth=980。所以这里只认「移动 UA」
 * 或「粗指针 + 屏幕短边 ≤ 900」（screen.width 是设备物理尺寸，不受视口影响）。
 *
 * 规则（与 src/lib/theme.js 的 isMobileLike 保持一致）：
 *   ① 用户手动选过（localStorage['cl:theme']）→ 照用户； *   ② 否则：移动端跟随系统深浅色（prefers-color-scheme）；
 *   ③ 其余（桌面）→ 浅色。
 */
(function () {
  try {
    var THEMES = ["light", "geek"];
    var t = null;
    try {
      t = localStorage.getItem("cl:theme");
    } catch (e) {
      t = null;
    }
    if (THEMES.indexOf(t) < 0) {
      var mm = window.matchMedia ? window.matchMedia.bind(window) : null;
      var ua = /Android|iPhone|iPad|iPod|Mobile|HarmonyOS|MiuiBrowser/i.test(navigator.userAgent || "");
      var coarse = mm ? mm("(pointer: coarse)").matches : false;
      var sc = window.screen || {};
      var shortSide = Math.min(sc.width || 0, sc.height || 0);
      var mobile = ua || (coarse && shortSide > 0 && shortSide <= 900);
      var dark = mm ? mm("(prefers-color-scheme: dark)").matches : false;
      t = mobile && dark ? "geek" : "light";
    }
    var root = document.documentElement;
    root.setAttribute("data-theme", t);
    // 调试用：记录「首帧脚本自己算出来的值」，和 React 挂载后的最终值分开看
    root.setAttribute("data-theme-boot", t);
    root.style.colorScheme = t === "geek" ? "dark" : "light";
  } catch (e) {
    /* 任何异常都退回 HTML 上写死的 light，不阻塞页面 */
  }
})();