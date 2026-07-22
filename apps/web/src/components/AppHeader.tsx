import { Database, FlaskConical, Menu, Network, Search } from "lucide-react";
import type { AppSection } from "../types";

type Props = {
  onOpenFilters: () => void;
  activeSection: AppSection;
  onNavigate: (section: AppSection) => void;
};

const NAV_ITEMS = [
  { key: "graph" as const, label: "图谱探索", icon: Network },
  { key: "matcher" as const, label: "岗位匹配", icon: FlaskConical },
  { key: "jobs" as const, label: "岗位目录", icon: Search },
  { key: "evidence" as const, label: "数据证据", icon: Database },
];

export function AppHeader({ onOpenFilters, activeSection, onNavigate }: Props) {
  return (
    <>
      <header className="app-header">
        <button className="mobile-menu" type="button" onClick={onOpenFilters} aria-label="打开筛选">
          <Menu size={20} />
        </button>
        <div className="brand">
          <span className="brand-mark"><Network size={19} /></span>
          <span>具身智能岗位能力图谱</span>
        </div>
        <nav className="primary-nav" aria-label="主导航">
          {NAV_ITEMS.map(({ key, label, icon: Icon }) => (
            <button className={activeSection === key ? "active" : ""} type="button" onClick={() => onNavigate(key)} key={key}>
              <Icon size={16} />{label}
            </button>
          ))}
        </nav>
        <div className="header-status"><span className="status-dot" />SQLite v4 · G6</div>
      </header>
      <nav className="mobile-primary-nav" aria-label="移动端主导航">
        {NAV_ITEMS.map(({ key, label, icon: Icon }) => (
          <button className={activeSection === key ? "active" : ""} type="button" onClick={() => onNavigate(key)} key={key}>
            <Icon size={15} />{label}
          </button>
        ))}
      </nav>
    </>
  );
}
