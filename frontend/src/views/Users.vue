<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>用户管理</span>
        <el-button type="primary" @click="openDialog()">添加用户</el-button>
      </div>
    </template>
    <el-table :data="users" stripe>
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="role" label="角色">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : row.role === 'operator' ? 'warning' : 'info'">{{ row.role }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="is_active" label="状态">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" @click="openDialog(row)">编辑</el-button>
          <el-popconfirm title="确定删除?" @confirm="deleteUser(row.id)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="showDialog" :title="form.id ? '编辑用户' : '添加用户'" width="400px">
    <el-form :model="form" label-width="80px">
      <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
      <el-form-item label="密码"><el-input v-model="form.password" type="password" :placeholder="form.id ? '留空不修改' : ''" /></el-form-item>
      <el-form-item label="角色">
        <el-select v-model="form.role">
          <el-option label="管理员" value="admin" />
          <el-option label="操作员" value="operator" />
          <el-option label="查看者" value="viewer" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showDialog = false">取消</el-button>
      <el-button type="primary" @click="saveUser">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const users = ref([])
const showDialog = ref(false)
const defaultForm = { id: null, username: '', password: '', role: 'viewer' }
const form = reactive({ ...defaultForm })

async function fetchUsers() {
  const { data } = await api.get('/api/users')
  users.value = data
}

function openDialog(row) {
  if (row) {
    Object.assign(form, { ...row, password: '' })
  } else {
    Object.assign(form, defaultForm)
  }
  showDialog.value = true
}

async function saveUser() {
  if (form.id) {
    const payload = { role: form.role }
    if (form.username) payload.username = form.username
    if (form.password) payload.password = form.password
    await api.put(`/api/users/${form.id}`, payload)
  } else {
    await api.post('/api/users', form)
  }
  showDialog.value = false
  Object.assign(form, defaultForm)
  fetchUsers()
  ElMessage.success('保存成功')
}

async function deleteUser(id) {
  await api.delete(`/api/users/${id}`)
  fetchUsers()
  ElMessage.success('删除成功')
}

onMounted(fetchUsers)
</script>
