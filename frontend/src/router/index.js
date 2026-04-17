import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { APP_TITLE } from '../brand'

const routes = [
  { path: '/login', name: 'Login', meta: { title: '登录' }, component: () => import('../views/Login.vue') },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'Dashboard', meta: { module: 'dashboard', title: '数据看板' }, component: () => import('../views/Dashboard.vue') },
      { path: 'orders', name: 'Orders', meta: { module: 'orders', title: '订单管理' }, component: () => import('../views/Orders.vue') },
      { path: 'orders/:id', name: 'OrderDetail', meta: { module: 'orders', title: '订单详情' }, component: () => import('../views/OrderDetail.vue') },
      { path: 'shop-products', name: 'ShopProducts', meta: { module: 'products', title: '产品管理' }, component: () => import('../views/ShopProducts.vue') },
      { path: 'products', name: 'Products', meta: { module: 'products', title: '商品管理' }, component: () => import('../views/Products.vue') },
      { path: 'purchase-plan', name: 'PurchasePlan', meta: { module: 'purchase_plan', title: '采购计划' }, component: () => import('../views/PurchasePlan.vue') },
      { path: 'ads', name: 'AdsOverview', meta: { module: 'ads', title: '推广数据' }, component: () => import('../views/AdsOverview.vue') },
      { path: 'ads/:id', name: 'AdDetail', meta: { module: 'ads', title: '推广详情' }, component: () => import('../views/AdDetail.vue') },
      { path: 'finance', name: 'Finance', meta: { module: 'finance', title: '财务统计' }, component: () => import('../views/Finance.vue') },
      { path: 'customer-service', name: 'CustomerService', meta: { module: 'customer_service', title: '评价客服' }, component: () => import('../views/CustomerService.vue') },
      { path: 'commission-shipping', name: 'CommissionShipping', meta: { module: 'commission_shipping', title: '佣金运费' }, component: () => import('../views/CommissionShipping.vue') },
      { path: 'inventory', name: 'Inventory', meta: { module: 'inventory', title: '库存管理' }, component: () => import('../views/Inventory.vue') },
      { path: 'shops', name: 'Shops', meta: { module: 'shops', title: '店铺管理' }, component: () => import('../views/Shops.vue') },
      { path: 'shops/:id/sku-mappings', name: 'SkuMappings', meta: { module: 'shops', title: 'SKU关联' }, component: () => import('../views/SkuMappings.vue') },
      { path: 'users', name: 'Users', meta: { module: 'users', adminOnly: true, title: '用户管理' }, component: () => import('../views/Users.vue') },
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
    return
  }

  // 权限检查
  if (token && to.meta.module) {
    const authStore = useAuthStore()
    // 确保用户信息已加载
    if (!authStore.user) {
      try {
        await authStore.fetchUser()
      } catch (e) {
        next('/login')
        return
      }
    }
    const user = authStore.user
    if (user) {
      // admin 可以访问所有模块
      if (user.role === 'admin') {
        next()
        return
      }
      // adminOnly 路由非 admin 不可访问
      if (to.meta.adminOnly) {
        next('/')
        return
      }
      // 检查模块权限
      const permissions = user.permissions || []
      if (!permissions.includes(to.meta.module)) {
        next('/')
        return
      }
    }
  }

  next()
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${APP_TITLE} - ${to.meta.title}` : APP_TITLE
})

export default router
