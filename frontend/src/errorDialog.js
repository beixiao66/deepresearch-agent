import { ref } from "vue"

const visible = ref(false)
const message = ref("")

export function showErrorDialog(error) {
  message.value =
    typeof error === "string"
      ? error
      : error?.message || "操作失败，请稍后重试"
  visible.value = true
}

export function closeErrorDialog() {
  visible.value = false
}

export function useErrorDialog() {
  return {
    visible,
    message,
    closeErrorDialog,
  }
}
