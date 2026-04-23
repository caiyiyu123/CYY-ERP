<template>
  <el-card>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="定价表" name="list">
        <PricingListTab />
      </el-tab-pane>
      <el-tab-pane label="参数" name="params">
        <ParamsTab />
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script setup>
import { ref } from 'vue'
import PricingListTab from '@/components/pricing/PricingListTab.vue'
import ParamsTab from '@/components/pricing/ParamsTab.vue'

const activeTab = ref('list')
</script>
