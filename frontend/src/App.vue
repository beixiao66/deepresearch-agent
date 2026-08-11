<script setup>
import { RouterLink, RouterView } from "vue-router"
import ErrorDialog from "./components/ErrorDialog.vue"
</script>

<template>
  <div class="app">
    <nav class="nav">
      <RouterLink to="/knowledge-bases">知识库</RouterLink>
      <RouterLink to="/research/create">创建研究</RouterLink>
      <RouterLink to="/research/tasks">研究历史</RouterLink>
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
}
.nav {
  display: flex;
  gap: 24px;
  padding: 16px 32px;
  background: #1a1a2e;
}
.nav a {
  color: #eee;
  text-decoration: none;
  font-size: 15px;
}
.nav a.router-link-active {
  color: #4fc3f7;
  font-weight: 600;
}
.main {
  padding: 24px 32px;
}
</style>
