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
  background: rgba(0, 0, 0, 0.45);
}
.error-dialog {
  width: min(420px, 100%);
  box-sizing: border-box;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 14px;
  padding: 20px;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.24);
}
.dialog-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #ffebee;
  color: #c62828;
  font-weight: 700;
}
.dialog-content h3 {
  margin: 1px 0 8px;
  color: #1a1a1a;
  font-size: 18px;
}
.dialog-content p {
  margin: 0;
  color: #555;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.error-dialog button {
  grid-column: 2;
  justify-self: end;
  min-width: 72px;
  padding: 8px 18px;
  border: 0;
  border-radius: 6px;
  background: #1976d2;
  color: #fff;
  cursor: pointer;
}
</style>
