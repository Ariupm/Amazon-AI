import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://caishu-amazon-insights.chumoiii.chatgpt.site"),
  title: "采数｜Amazon 真实商品数据采集器",
  description: "真实浏览器采集 Amazon 父子体、月销量信号、评论优痛点，并导出图片版 XLSX。",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "采数｜Amazon 真实商品数据采集器",
    description: "父子体 · 月销量 · 评论洞察 · XLSX",
    images: ["/og.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "采数｜Amazon 真实商品数据采集器",
    description: "父子体 · 月销量 · 评论洞察 · XLSX",
    images: ["/og.png"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
