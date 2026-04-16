<template>
  <div
    ref="zoneRef"
    class="img-uploader"
    tabindex="0"
    @paste="onPaste"
    @dragover.prevent
    @drop.prevent="onDrop"
    @click.self="zoneRef?.focus()"
  >
    <div v-if="preview" style="position: relative; display: inline-block">
      <el-image :src="preview" :style="{ width: size + 'px', height: size + 'px', borderRadius: '6px' }" fit="cover" />
      <el-button type="danger" :icon="Remove" circle size="small" style="position: absolute; top: -8px; right: -8px" @click.stop="remove" />
    </div>
    <div v-if="preview" style="margin-top: 8px; color: #999; font-size: 12px">点击空白处后 Ctrl+V 粘贴替换</div>
    <div v-else style="display: flex; flex-direction: column; align-items: center; gap: 8px">
      <el-upload :auto-upload="false" :show-file-list="false" accept="image/*" :on-change="onChange">
        <el-button type="primary" plain><el-icon style="margin-right: 4px"><UploadFilled /></el-icon>上传图片</el-button>
      </el-upload>
      <span style="color: #999; font-size: 12px">或拖拽图片到此处 / Ctrl+V 粘贴</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { UploadFilled, Remove } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  size: { type: Number, default: 120 },
})

const emit = defineEmits(['update:modelValue', 'file-change', 'remove'])

const zoneRef = ref(null)
const preview = ref(props.modelValue)
const pendingFile = ref(null)

watch(() => props.modelValue, (val) => {
  if (!pendingFile.value) preview.value = val
})

function setFile(file) {
  pendingFile.value = file
  if (preview.value && preview.value.startsWith('blob:')) URL.revokeObjectURL(preview.value)
  preview.value = URL.createObjectURL(file)
  emit('file-change', file)
}

function remove() {
  if (preview.value && preview.value.startsWith('blob:')) URL.revokeObjectURL(preview.value)
  preview.value = ''
  pendingFile.value = null
  emit('update:modelValue', '')
  emit('remove')
}

function onChange(file) { setFile(file.raw) }

function onPaste(e) {
  const items = e.clipboardData?.items
  if (!items) return
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      e.preventDefault()
      const file = item.getAsFile()
      if (file) setFile(file)
      return
    }
  }
}

function onDrop(e) {
  const file = e.dataTransfer?.files?.[0]
  if (file?.type.startsWith('image/')) setFile(file)
}

defineExpose({ pendingFile, preview })
</script>

<style scoped>
.img-uploader {
  width: 100%;
  min-height: 160px;
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  outline: none;
  transition: border-color 0.2s;
}
.img-uploader:hover,
.img-uploader:focus {
  border-color: #409eff;
}
</style>
