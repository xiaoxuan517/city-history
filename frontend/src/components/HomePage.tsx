import {
  Archive,
  BookOpen,
  Bot,
  Camera,
  Download,
  FileSearch,
  LibraryBig,
  MapPinned,
  Search,
  Sparkles,
} from "lucide-react";

import SiteNav from "./SiteNav";

type HomePageProps = {
  apiStatus: string;
  isAuthenticated: boolean;
  username?: string;
  onEnterLibrary: () => void;
  onEnterKnowledgeBase: () => void;
  onEnterAssistant: () => void;
  onEnterHistoryAlbum: () => void;
  onEnterFavorites: () => void;
  onLogin: () => void;
  onLogout: () => void;
};

const featuredBooks = [
  {
    title: "金陵图咏",
    region: "江南府县",
    dynasty: "明天启二年",
    pages: "40 幅图咏",
    status: "可浏览",
  },
  {
    title: "华阳县志",
    region: "四川成都府",
    dynasty: "清代刊本",
    pages: "地理 / 建置 / 人物",
    status: "建设中",
  },
  {
    title: "长安县志",
    region: "陕西西安府",
    dynasty: "民国重修",
    pages: "舆图 / 祠祀 / 艺文",
    status: "可问答",
  },
  {
    title: "吴县志",
    region: "江苏苏州府",
    dynasty: "清乾隆本",
    pages: "山川 / 水利 / 学校",
    status: "可下载",
  },
];

const stats = [
  ["2,418", "县志条目"],
  ["138 万", "页影像与文本"],
  ["342", "地域索引"],
  ["24 小时", "在线问答"],
];

function HomePage({
  apiStatus,
  isAuthenticated,
  username,
  onEnterLibrary,
  onEnterKnowledgeBase,
  onEnterAssistant,
  onEnterHistoryAlbum,
  onEnterFavorites,
  onLogin,
  onLogout,
}: HomePageProps) {
  return (
    <main className="heritage-home">
      <SiteNav
        active="home"
        isAuthenticated={isAuthenticated}
        username={username}
        onHome={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        onGazetteers={onEnterLibrary}
        onKnowledgeBase={onEnterKnowledgeBase}
        onAssistant={onEnterAssistant}
        onHistoryAlbum={onEnterHistoryAlbum}
        onFavorites={onEnterFavorites}
        onLogin={onLogin}
        onLogout={onLogout}
      />

      <section className="home-hero">
        <div className="hero-copy">
          <p className="home-eyebrow">中国古籍县志数字化平台</p>
          <h1>把散落在卷册中的地方记忆，变成可浏览、可下载、可追问的知识库。</h1>
          <p className="hero-lead">
            面向县志、府志、乡土志等地方文献，提供古籍目录展示、影像在线浏览、原文下载与 RAG
            问答。读者可以按地域、朝代、主题查找文献，也可以针对单本县志建立知识库，追问山川、建置、人物、艺文与风俗。
          </p>
          <div className="hero-actions">
            <button className="home-primary" type="button" onClick={onEnterLibrary}>
              <BookOpen size={18} />
              浏览县志
            </button>
            <button className="home-secondary" type="button" onClick={onEnterKnowledgeBase}>
              <Bot size={18} />
              创建问答知识库
            </button>
            <button className="home-secondary" type="button" onClick={onEnterAssistant}>
              <Sparkles size={18} />
              智能检索下载
            </button>
            <button className="home-secondary" type="button" onClick={onEnterHistoryAlbum}>
              <Camera size={18} />
              浏览历史图册
            </button>
          </div>
          <div className="hero-status">
            <span className={apiStatus === "可用" ? "status-dot ok" : "status-dot bad"} />
            API {apiStatus}
          </div>
        </div>

        <figure className="hero-art">
          <img
            src="https://upload.wikimedia.org/wikipedia/commons/2/21/Gazetteer_of_Nanjing%2C_1624.jpg"
            alt="明代金陵图咏木刻插图"
          />
          <figcaption>《金陵图咏》木刻插图，1624 年</figcaption>
        </figure>
      </section>

      <section className="stat-band" aria-label="平台统计">
        {stats.map(([value, label]) => (
          <div key={label}>
            <strong>{value}</strong>
            <span>{label}</span>
          </div>
        ))}
      </section>

      <section className="home-section">
        <div className="section-head">
          <p className="home-eyebrow">核心能力</p>
          <h2>从看见古籍，到读懂一县之史</h2>
        </div>
        <div className="feature-grid">
          <article>
            <LibraryBig size={26} />
            <h3>县志总目</h3>
            <p>按省府州县、成书年代、版本形态与主题门类组织古籍，适合快速定位地方文献。</p>
          </article>
          <article>
            <FileSearch size={26} />
            <h3>在线浏览</h3>
            <p>面向影像页、目录层级和文本片段设计阅读入口，保留古籍版面，同时支持现代检索。</p>
          </article>
          <article>
            <Download size={26} />
            <h3>下载与引用</h3>
            <p>为研究、教学和地方文化整理提供稳定下载入口，便于离线校读、摘录和引用。</p>
          </article>
          <article>
            <Sparkles size={26} />
            <h3>单本 RAG 问答</h3>
            <p>为每一本古籍建立独立知识库，回答时返回来源片段，降低跨书混淆和无出处解释。</p>
          </article>
        </div>
      </section>

      <section className="workflow-section">
        <div>
          <p className="home-eyebrow">使用路径</p>
          <h2>围绕一本县志完成研究闭环</h2>
        </div>
        <div className="workflow-list">
          <span>选择县志</span>
          <span>浏览影像与目录</span>
          <span>下载原文</span>
          <span>建立知识库</span>
          <span>追问并核验出处</span>
        </div>
      </section>

      <section id="county-gazetteers" className="home-section">
        <div className="section-head split">
          <div>
            <p className="home-eyebrow">古籍选览</p>
            <h2>部分县志与地方文献</h2>
          </div>
          <button className="home-secondary compact" type="button" onClick={onEnterLibrary}>
            <Search size={17} />
            查看更多
          </button>
        </div>
        <div className="book-grid">
          {featuredBooks.map((book) => (
            <article className="book-card" key={book.title}>
              <div className="book-cover">
                <Archive size={34} />
                <span>{book.status}</span>
              </div>
              <div className="book-info">
                <h3>{book.title}</h3>
                <p>{book.region}</p>
                <dl>
                  <div>
                    <dt>年代</dt>
                    <dd>{book.dynasty}</dd>
                  </div>
                  <div>
                    <dt>内容</dt>
                    <dd>{book.pages}</dd>
                  </div>
                </dl>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="map-section">
        <MapPinned size={30} />
        <div>
          <p className="home-eyebrow">地域知识网络</p>
          <h2>以县域为单位连接地名、人物、艺文与制度沿革</h2>
          <p>
            平台后续可继续接入地名规范库、行政区划沿革、人物关系和版本目录，把单本古籍问答扩展为跨地域的地方知识发现。
          </p>
        </div>
      </section>

      <footer className="home-footer">
        <div>
          <strong>方志云藏</strong>
          <p>中国古籍县志展示、浏览、下载与 RAG 问答平台。</p>
        </div>
        <p>
          首页图像来源：Wikimedia Commons《Gazetteer of Nanjing, 1624》，Public Domain Mark。
        </p>
      </footer>
    </main>
  );
}

export default HomePage;
