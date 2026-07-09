import { Landmark } from "lucide-react";

import UserMenu from "./UserMenu";

export type SiteNavKey = "home" | "gazetteers" | "knowledgeBase" | "assistant" | "historyAlbum" | "favorites";

type SiteNavProps = {
  active: SiteNavKey;
  isAuthenticated: boolean;
  username?: string;
  onHome: () => void;
  onGazetteers: () => void;
  onKnowledgeBase: () => void;
  onAssistant: () => void;
  onHistoryAlbum: () => void;
  onFavorites: () => void;
  onLogin: () => void;
  onLogout: () => void;
};

function SiteNav({
  active,
  isAuthenticated,
  username,
  onHome,
  onGazetteers,
  onKnowledgeBase,
  onAssistant,
  onHistoryAlbum,
  onFavorites,
  onLogin,
  onLogout,
}: SiteNavProps) {
  return (
    <nav className="site-nav" aria-label="主导航">
      <button className="nav-brand" type="button" onClick={onHome}>
        <Landmark size={24} />
        <span>方志云藏</span>
      </button>
      <div className="nav-links">
        <button type="button" className={active === "gazetteers" ? "active" : undefined} onClick={onGazetteers}>
          县志
        </button>
        <button type="button" className={active === "knowledgeBase" ? "active" : undefined} onClick={onKnowledgeBase}>
          知识库
        </button>
        <button type="button" className={active === "assistant" ? "active" : undefined} onClick={onAssistant}>
          智能助手
        </button>
        <button type="button" className={active === "historyAlbum" ? "active" : undefined} onClick={onHistoryAlbum}>
          历史图册
        </button>
        <button type="button" className={active === "favorites" ? "active" : undefined} onClick={onFavorites}>
          我的收藏
        </button>
      </div>
      <UserMenu isAuthenticated={isAuthenticated} username={username} onLogin={onLogin} onLogout={onLogout} />
    </nav>
  );
}

export default SiteNav;
