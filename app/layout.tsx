import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "采数｜Amazon 商品数据获取工具",
  description: "输入 ASIN，快速获取商品、父子变体与评论优缺点洞察。",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
