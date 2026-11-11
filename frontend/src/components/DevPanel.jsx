// 临时设计调试面板：只在本机 ?dev=1 时挂载（App.jsx 的挂载点也做了同一道门）。
// 三组开关都直接写 <html> 上的 data-*，所以是「立刻生效」：
//   data-icon-style → IconSet.jsx 的 PolarityIcon（React 订阅）
//   data-stamp      → Stamp.jsx（React 订阅）
//   data-font       → 纯 CSS，devpanel.css 里的变量覆写
// 收起后只剩右下角一个小圆钮，不挡内容。
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { getDevSetting, setDevSetting, useDevSetting, KIND_LABEL, PolarityIcon } from "./IconSet.jsx";
import "../devpanel.css";

const DEV = () => new URLSearchParams(location.search).get("dev") === "1";

const ICON_OPTIONS = [
  { value: "a", label: "A", full: "A · 线性（现有）" },
  { value: "b", label: "B", full: "B · 实心填充" },
  { value: "c", label: "C", full: "C · 手绘不规则" },
  { value: "d", label: "D", full: "D · 印刷双线" },
];
const FONT_OPTIONS = [
  { value: "a", label: "甲", full: "甲 · 当前：楷体标题 + 黑体正文" },
  { value: "b", label: "乙", full: "乙 · 全楷体：标题与正文都用霞鹜文楷" },
  { value: "c", label: "丙", full: "丙 · 标题黑体加粗，数字/元数据保留衬线与等宽" },
];
const STAMP_OPTIONS = [
  { value: "1", label: "圆环", full: "1 · 圆形双环（现有）" },
  { value: "2", label: "方章", full: "2 · 中式方形印章" },
  { value: "3", label: "叠印", full: "3 · 双色叠印（错位叠加）" },
];
const KINDS = ["warning", "good", "neutral", "question"];

function Group({ title, value, onChange, options }) {
  return (
    <fieldset className="devpanel__group">
      <legend className="devpanel__legend">{title}</legend>
      <div className="devpanel__seg">
        {options.map((o) => {
          const on = value === o.value;
          return (
            <label key={o.value} className={`devpanel__opt${on ? " is-on" : ""}`} title={o.full || o.label}>
              <input type="radio" name={`dev-${title}`} value={o.value} checked={on} onChange={() => onChange(o.value)} />
              <span>{o.label}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

export default function DevPanel() {
  const [open, setOpen] = useState(true);
  // 选项状态就在 <html data-*> 上：面板只读它，所以控制台 / 截图脚本外部改属性时面板也跟着走
  const icon = useDevSetting("iconStyle");
  const font = useDevSetting("font");
  const stamp = useDevSetting("stamp");

  // 首次挂载把默认值显式落到 dataset 上（不然 CSS 里没有 [data-font]，看不出「甲」也是被选中的）
  useEffect(() => {
    setDevSetting("iconStyle", getDevSetting("iconStyle"));
    setDevSetting("font", getDevSetting("font"));
    setDevSetting("stamp", getDevSetting("stamp"));
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [open]);

  if (!DEV()) return null;

  const reset = () => {
    setDevSetting("iconStyle", "a");
    setDevSetting("font", "a");
    setDevSetting("stamp", "1");
  };

  const node = (
    <div className={`devpanel${open ? " is-open" : ""}`}>
      {open ? (
        <div className="devpanel__card" role="group" aria-label="设计调试面板">
          <div className="devpanel__head">
            <span className="devpanel__title">
              DEV<span className="devpanel__dot" />设计调试
            </span>
            <span className="devpanel__tools">
              <button type="button" className="devpanel__link" onClick={reset}>
                复位
              </button>
              <button type="button" className="devpanel__close" onClick={() => setOpen(false)} aria-label="收起面板" title="收起（Esc）">
                ×
              </button>
            </span>
          </div>

          <Group title="图标" value={icon} onChange={(v) => setDevSetting("iconStyle", v)} options={ICON_OPTIONS} />
          <div className="devpanel__preview" aria-label="当前图标风格预览">
            {KINDS.map((k) => (
              <span key={k} className="devpanel__pv">
                <PolarityIcon kind={k} style={icon.toUpperCase()} width={16} height={16} />
                <em>{KIND_LABEL[k]}</em>
              </span>
            ))}
          </div>

          <Group title="字体" value={font} onChange={(v) => setDevSetting("font", v)} options={FONT_OPTIONS} />
          <Group title="印章" value={stamp} onChange={(v) => setDevSetting("stamp", v)} options={STAMP_OPTIONS} />

          <p className="devpanel__foot">?dev=1 · 只改本机显示，不影响正常访问</p>
        </div>
      ) : (
        <button type="button" className="devpanel__fab" onClick={() => setOpen(true)} aria-label="打开设计调试面板" title="设计调试面板">
          <span className="devpanel__fablbl">DEV</span>
          <span className="devpanel__fabval">
            {icon.toUpperCase()}
            {font.toUpperCase()}
            {stamp}
          </span>
        </button>
      )}
    </div>
  );

  return createPortal(node, document.body);
}