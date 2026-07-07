type UserMenuProps = {
  isAuthenticated: boolean;
  username?: string;
  onLogin: () => void;
  onLogout: () => void;
};

function UserMenu({ isAuthenticated, username, onLogin, onLogout }: UserMenuProps) {
  if (!isAuthenticated) {
    return (
      <button className="nav-login" type="button" onClick={onLogin}>
        登录
      </button>
    );
  }

  return (
    <details className="nav-user-menu">
      <summary className="nav-login">{username || "用户"}</summary>
      <div className="nav-user-dropdown">
        <button type="button" onClick={onLogout}>
          退出登录
        </button>
      </div>
    </details>
  );
}

export default UserMenu;
