import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "THREAD AUTO 개인 강의 사전조사",
  description: "운영 중인 쇼핑 제휴 콘텐츠 자동화 프로그램의 개인 강의·원격지원·PDF 구성을 위한 사전조사",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
