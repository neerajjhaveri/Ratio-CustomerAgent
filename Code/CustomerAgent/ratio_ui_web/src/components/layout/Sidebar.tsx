import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import Nav from 'react-bootstrap/Nav';
import Button from 'react-bootstrap/Button';
import Collapse from 'react-bootstrap/Collapse';

const EXPANDED_WIDTH = 240;
const COLLAPSED_WIDTH = 64;

const linkStyle = (collapsed: boolean, isActive: boolean) => ({
  display: 'flex' as const,
  alignItems: 'center' as const,
  gap: collapsed ? 0 : 10,
  justifyContent: collapsed ? ('center' as const) : ('flex-start' as const),
  padding: collapsed ? '0.5rem 0' : '0.5rem 1rem',
  margin: '1px 12px',
  borderRadius: 6,
  color: '#fff',
  fontWeight: isActive ? 600 : 400,
  fontSize: '0.9rem',
  background: isActive ? 'rgba(255,255,255,0.18)' : 'transparent',
  whiteSpace: 'nowrap' as const,
});

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const isFuseSection = location.pathname.startsWith('/fuse');
  const [fuseOpen, setFuseOpen] = useState(isFuseSection);
  const width = collapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH;

  return (
    <div
      className="d-flex flex-column text-white"
      style={{
        width,
        minWidth: width,
        height: '100vh',
        backgroundImage: 'linear-gradient(180deg, #1e3c72 0%, #2a5298 100%)',
        transition: 'width 0.3s ease, min-width 0.3s ease',
        overflow: 'hidden',
        position: 'sticky',
        top: 0,
      }}
    >
      {/* Logo header */}
      <div
        className="d-flex align-items-center justify-content-center position-relative"
        style={{
          padding: collapsed ? '0.75rem 0.5rem' : '1.25rem 1.25rem',
          borderBottom: '1px solid rgba(255,255,255,0.15)',
          background: 'rgba(0,0,0,0.4)',
          cursor: collapsed ? 'pointer' : 'default',
        }}
        onClick={collapsed ? () => setCollapsed(false) : undefined}
        title={collapsed ? 'Expand sidebar' : undefined}
      >
        <img
          src={collapsed ? '/favicon.png' : '/RATIO-W.svg'}
          alt="Ratio AI"
          style={{ height: collapsed ? 32 : 44, width: 'auto', transition: 'height 0.3s' }}
        />
        {!collapsed && (
          <Button
            variant="link"
            className="text-white-50 p-1"
            style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', borderRadius: 6 }}
            onClick={() => setCollapsed(true)}
            title="Collapse sidebar"
          >
            <i className="bi bi-chevron-double-left" style={{ fontSize: 16 }} />
          </Button>
        )}
      </div>

      {/* Navigation */}
      <Nav className="flex-column flex-grow-1 py-2">
        {/* Home */}
        <Nav.Item>
          <NavLink
            to="/"
            end
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            style={({ isActive }) => linkStyle(collapsed, isActive)}
          >
            <i className="bi bi-house-door" style={{ fontSize: 18 }} />
            {!collapsed && <span>Home</span>}
          </NavLink>
        </Nav.Item>

        {/* SR Insights */}
        <Nav.Item>
          <NavLink
            to="/sr-insights"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            style={({ isActive }) => linkStyle(collapsed, isActive)}
          >
            <i className="bi bi-graph-up" style={{ fontSize: 18 }} />
            {!collapsed && <span>Service Impact</span>}
          </NavLink>
        </Nav.Item>

        {/* Fuse — parent links to overview, expandable sub-items */}
        <Nav.Item>
          {collapsed ? (
            <NavLink
              to="/fuse"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              style={() => linkStyle(collapsed, isFuseSection)}
              title="Ratio Fuse"
            >
              <i className="bi bi-diagram-3" style={{ fontSize: 18 }} />
            </NavLink>
          ) : (
            <>
              <NavLink
                to="/fuse"
                end
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                onClick={(e) => {
                  if (isFuseSection) {
                    // Already in fuse section — just toggle submenu, don't navigate
                    e.preventDefault();
                    setFuseOpen(!fuseOpen);
                  } else {
                    setFuseOpen(true);
                  }
                }}
                style={({ isActive }) => ({
                  ...linkStyle(false, isActive),
                  background: isActive
                    ? 'rgba(255,255,255,0.18)'
                    : isFuseSection
                      ? 'rgba(255,255,255,0.08)'
                      : 'transparent',
                  cursor: 'pointer',
                })}
              >
                <i className="bi bi-diagram-3" style={{ fontSize: 18 }} />
                <span className="flex-grow-1">Ratio Fuse</span>
                <i
                  className={`bi bi-chevron-${fuseOpen ? 'up' : 'down'}`}
                  style={{ fontSize: 12, opacity: 0.6 }}
                />
              </NavLink>
              <Collapse in={fuseOpen}>
                <div>
                  <NavLink
                    to="/fuse/studio"
                    className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                    style={({ isActive }) => ({
                      ...linkStyle(false, isActive),
                      paddingLeft: '2.75rem',
                      fontSize: '0.9rem',
                    })}
                  >
                    <i className="bi bi-play-circle" style={{ fontSize: 15 }} />
                    <span>Fuse Studio</span>
                  </NavLink>
                </div>
              </Collapse>
            </>
          )}
        </Nav.Item>

        {/* Agent DevUI */}
        <Nav.Item>
          <NavLink
            to="/agent-devui"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            style={({ isActive }) => linkStyle(collapsed, isActive)}
          >
            <i className="bi bi-robot" style={{ fontSize: 18 }} />
            {!collapsed && <span>Agent DevUI</span>}
          </NavLink>
        </Nav.Item>

        {/* DevUI Studio (embedded) */}
        <Nav.Item>
          <NavLink
            to="/devui-studio"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            style={({ isActive }) => linkStyle(collapsed, isActive)}
          >
            <i className="bi bi-terminal" style={{ fontSize: 18 }} />
            {!collapsed && <span>DevUI Studio</span>}
          </NavLink>
        </Nav.Item>

        {/* CustomerAgent Investigation */}
        <Nav.Item>
          <NavLink
            to="/customer-agent"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            style={({ isActive }) => linkStyle(collapsed, isActive)}
          >
            <i className="bi bi-heart-pulse" style={{ fontSize: 18 }} />
            {!collapsed && <span>Customer Agent</span>}
          </NavLink>
        </Nav.Item>
      </Nav>
    </div>
  );
}
