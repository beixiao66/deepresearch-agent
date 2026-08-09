import { createRouter, createWebHistory } from "vue-router"

const history = createWebHistory()

import KnowledgeBases from "./views/KnowledgeBases.vue"
import CreateResearch from "./views/CreateResearch.vue"
import ResearchRun from "./views/ResearchRun.vue"
import ResearchReport from "./views/ResearchReport.vue"
import ResearchTasks from "./views/ResearchTasks.vue"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/knowledge-bases" },
    { path: "/knowledge-bases", component: KnowledgeBases },
    { path: "/research/create", component: CreateResearch },
    { path: "/research/run/:taskId", component: ResearchRun },
    { path: "/research/report/:taskId", component: ResearchReport },
    { path: "/research/tasks", component: ResearchTasks },
  ],
})

export default router
