<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>订单列表</span>
        <div style="display: flex; gap: 12px">
          <el-select v-model="filters.order_type" placeholder="订单类型" clearable @change="fetchOrders">
            <el-option label="FBS" value="FBS" />
            <el-option label="FBW" value="FBW" />
          </el-select>
          <el-select v-model="filters.status" placeholder="状态" clearable @change="fetchOrders">
            <el-option label="待发货" value="pending" />
            <el-option label="已发货" value="shipped" />
            <el-option label="配送中" value="in_transit" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
            <el-option label="已退货" value="returned" />
          </el-select>
        </div>
      </div>
    </template>
    <el-table :data="orders" stripe style="cursor: pointer" @row-click="row => $router.push(`/orders/${row.id}`)">
      <el-table-column prop="wb_order_id" label="订单号" />
      <el-table-column prop="order_type" label="类型">
        <template #default="{ row }">
          <el-tag :type="row.order_type === 'FBS' ? 'success' : 'primary'" size="small">{{ row.order_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_price" label="金额">
        <template #default="{ row }">₽ {{ row.total_price?.toLocaleString() }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" />
      <el-table-column prop="warehouse_name" label="仓库" />
      <el-table-column prop="created_at" label="时间" />
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="50" layout="total, prev, pager, next" style="margin-top: 16px" @current-change="fetchOrders" />
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'

const route = useRoute()
const orders = ref([])
const total = ref(0)
const page = ref(1)
const filters = reactive({ order_type: route.query.order_type || '', status: '' })

async function fetchOrders() {
  const params = { page: page.value }
  if (filters.order_type) params.order_type = filters.order_type
  if (filters.status) params.status = filters.status
  const { data } = await api.get('/api/orders', { params })
  orders.value = data.items
  total.value = data.total
}

onMounted(fetchOrders)
</script>
