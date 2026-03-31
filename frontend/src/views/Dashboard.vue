<template>
  <div>
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #999; font-size: 14px">今日订单</div>
          <div style="font-size: 28px; font-weight: bold">{{ stats.today_orders }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #999; font-size: 14px">今日销售额</div>
          <div style="font-size: 28px; font-weight: bold">₽ {{ stats.today_sales?.toLocaleString() }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #999; font-size: 14px">待发货</div>
          <div style="font-size: 28px; font-weight: bold; color: #f57c00">{{ stats.pending_shipment }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #999; font-size: 14px">低库存预警</div>
          <div style="font-size: 28px; font-weight: bold; color: #c62828">{{ stats.low_stock_count }}</div>
        </el-card>
      </el-col>
    </el-row>
    <el-card style="margin-bottom: 20px">
      <template #header>最近订单</template>
      <el-table :data="stats.recent_orders" stripe>
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
        <el-table-column prop="created_at" label="时间" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const stats = ref({ today_orders: 0, today_sales: 0, pending_shipment: 0, low_stock_count: 0, recent_orders: [] })

onMounted(async () => {
  const { data } = await api.get('/api/dashboard/stats')
  stats.value = data
})
</script>
