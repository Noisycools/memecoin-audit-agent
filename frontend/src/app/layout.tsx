import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "Memecoin Audit Agent · GMGN Scout + 9router AI",
  description:
    "Sistem pemindaian dan audit memecoin Solana otomatis dengan GMGN Scout & 9router AI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id" className="dark">
      <body className="min-h-screen flex flex-col bg-[#090d16] text-slate-100 antialiased">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">
          {children}
        </main>
        <footer className="border-t border-slate-800/80 bg-slate-950 py-4 px-4 text-center text-xs text-slate-400">
          <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
            <span>
              <b>Disclaimer:</b> Analisis otomatis, bukan nasihat keuangan.
              Memecoin berisiko kehilangan seluruh modal.
            </span>
            <span>
              Heuristik wash trade dari DexScreener bersifat proksi · Skor adalah
              potret saat pemindaian
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
