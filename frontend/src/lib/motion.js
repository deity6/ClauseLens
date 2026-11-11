// 全站动效令牌：缓动四件套 + 四档时长（frontend.md §3）。禁止在组件里现编 bezier。
export const EASE = {
  out: [0.22, 1, 0.36, 1], // 默认减速：状态切换、位移
  enter: [0.2, 0.7, 0.3, 1], // 进入：前段快，落位稳
  spring: [0.34, 1.56, 0.64, 1], // 回弹：只给缩放 / 弹入
  tail: [0.22, 0.61, 0.12, 1], // 长尾：只给进度 / 填充 / 数字滚动，位移缩放禁用
};

export const DUR = {
  micro: 0.16, // hover、按下、勾选
  state: 0.32, // 状态切换、展开收起
  enter: 0.52, // 进场
  stamp: 0.7, // 印章
};

// 整页三态过渡：旧态上移淡出；新态自下而上，越过 4px 再落回，给收束留一点尾韵
export const pageVariants = {
  initial: { opacity: 0, y: 32 },
  animate: {
    opacity: 1,
    y: [32, -4, 0],
    transition: { duration: DUR.enter + 0.12, ease: EASE.out, times: [0, 0.72, 1], opacity: { duration: DUR.enter, ease: EASE.enter } },
  },
  exit: { opacity: 0, y: -24, transition: { duration: DUR.state, ease: EASE.out } },
};
