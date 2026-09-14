<script setup>
import { RouterLink, RouterView } from "vue-router"
import ErrorDialog from "./components/ErrorDialog.vue"
</script>

<template>
  <div class="app">
    <nav class="nav">
      <div class="nav-inner">
        <RouterLink to="/knowledge-bases" class="brand">
          <span class="brand-mark">◆</span>
          DeepResearch<span class="brand-accent">Agent</span>
        </RouterLink>
        <div class="nav-links">
          <RouterLink to="/knowledge-bases">知识库</RouterLink>
          <RouterLink to="/research/create">创建研究</RouterLink>
          <RouterLink to="/research/tasks">研究历史</RouterLink>
          <RouterLink to="/chat">对话</RouterLink>
        </div>
      </div>
    </nav>
    <main class="main">
      <RouterView />
    </main>
    <ErrorDialog />
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  background: var(--bg);
}

.nav {
  position: sticky;
  top: 0;
  z-index: 20;
  border-bottom: 1px solid var(--border);
  background: rgba(11, 14, 20, 0.92);
  backdrop-filter: blur(8px);
}

.nav-inner {
  display: flex;
  align-items: center;
  gap: 28px;
  max-width: 1180px;
  height: 56px;
  margin: 0 auto;
  padding: 0 24px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text);
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
}
.brand:hover {
  text-decoration: none;
}
.brand-mark {
  color: var(--accent);
  font-size: 12px;
}
.brand-accent {
  color: var(--accent);
}

.nav-links {
  display: flex;
  gap: 4px;
}
.nav-links a {
  padding: 6px 12px;
  border-radius: 8px;
  color: var(--text-dim);
  font-size: 13px;
  text-decoration: none;
  transition: background 0.15s, color 0.15s;
}
.nav-links a:hover {
  background: var(--bg-elevated);
  color: var(--text);
  text-decoration: none;
}
.nav-links a.router-link-active {
  background: var(--accent-dim);
  color: var(--accent);
  font-weight: 600;
}

.main {
  max-width: 1180px;
  margin: 0 auto;
  padding: 28px 24px 64px;
}

@media (max-width: 720px) {
  .nav-inner {
    height: auto;
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
    padding: 12px 16px;
  }
  .main {
    padding: 20px 16px 48px;
  }
}
</style>
