<script setup>
import { useErrorDialog } from "../errorDialog"

const { visible, message, closeErrorDialog } = useErrorDialog()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="dialog-backdrop"
      @click.self="closeErrorDialog"
    >
      <div
        class="error-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="error-dialog-title"
      >
        <div class="dialog-icon">!</div>
        <div class="dialog-content">
          <h3 id="error-dialog-title">操作失败</h3>
          <p>{{ message }}</p>
        </div>
        <button type="button" @click="closeErrorDialog">
          确定
        </button>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(3, 5, 9, 0.62);
  backdrop-filter: blur(2px);
}
.error-dialog {
  width: min(420px, 100%);
  box-sizing: border-box;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 14px;
  padding: 20px;
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 12px;
  background: var(--bg-panel);
  box-shadow: 0 20px 48px rgba(0, 0, 0, 0.5);
}
.dialog-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(248, 113, 113, 0.14);
  color: var(--danger);
  font-weight: 700;
}
.dialog-content h3 {
  margin: 1px 0 8px;
  color: var(--text);
  font-size: 16px;
}
.dialog-content p {
  margin: 0;
  color: var(--text-dim);
  font-size: 13.5px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.error-dialog button {
  grid-column: 2;
  justify-self: end;
  min-width: 72px;
  margin-top: 4px;
}
</style>
