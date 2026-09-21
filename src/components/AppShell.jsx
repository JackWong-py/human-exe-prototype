// The frame around every page: the decorative circles, the orange header with the menu,
// and the white window that holds the page.

const TABS = [
  ["dashboard", "Dashboard"],
  ["checks", "Document checks"],
  ["reviews", "Review queue"],
  ["draft", "Draft reply"],
]

// Big ring, navy dot and second ring, like the design picture. They are only decoration.
function Backdrop() {
  return (
    <>
      <div className="pointer-events-none absolute -left-24 top-16 size-[26rem] rounded-full border-[3.5rem] border-[#f7962e]" />
      <div className="pointer-events-none absolute left-[30%] top-6 size-24 rounded-full bg-[#2b2d5c] shadow-xl" />
      <div className="pointer-events-none absolute -right-20 -top-16 size-64 rounded-full border-[3rem] border-[#f7962e]" />
    </>
  )
}

export default function AppShell({ page, onNavigate, children }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#e8eee9] px-4 py-10">
      <Backdrop />
      <div className="relative mx-auto max-w-6xl overflow-hidden rounded-2xl bg-background shadow-[0_30px_80px_-30px_rgba(43,45,92,0.35)]">
        <div className="bg-brand-gradient absolute inset-x-0 top-0 h-72" />

        <header className="relative flex flex-wrap items-center justify-between gap-4 px-10 pt-8 text-white">
          <nav className="flex flex-wrap gap-2">
            {TABS.map(([key, label]) => (
              <button
                key={key}
                onClick={() => onNavigate(key)}
                className={
                  "rounded-md px-4 py-2 text-sm font-semibold transition " +
                  (page === key ? "bg-white/25" : "text-white/80 hover:bg-white/15")
                }
              >
                {label}
              </button>
            ))}
          </nav>
          <div className="flex items-center gap-3 text-sm font-semibold">
            <span className="grid size-9 place-items-center rounded-full bg-[#2b2d5c] text-xs">HR</span>
            Human reviewer
          </div>
        </header>
        <div className="relative mx-10 mt-4 border-t border-white/40" />

        <main className="relative px-10 pb-10 pt-6">{children}</main>
      </div>
    </div>
  )
}
