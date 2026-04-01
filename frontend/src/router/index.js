import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue') },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'orders', name: 'Orders', component: () => import('../views/Orders.vue') },
      { path: 'orders/:id', name: 'OrderDetail', component: () => import('../views/OrderDetail.vue') },
      { path: 'products', name: 'Products', component: () => import('../views/Products.vue') },
      { path: 'ads', name: 'AdsOverview', component: () => import('../views/AdsOverview.vue') },
      { path: 'ads/:id', name: 'AdDetail', component: () => import('../views/AdDetail.vue') },
      { path: 'finance', name: 'Finance', component: () => import('../views/Finance.vue') },
      { path: 'inventory', name: 'Inventory', component: () => import('../views/Inventory.vue') },
      { path: 'shops', name: 'Shops', component: () => import('../views/Shops.vue') },
      { path: 'shops/:id/sku-mappings', name: 'SkuMappings', component: () => import('../views/SkuMappings.vue') },
      { path: 'users', name: 'Users', component: () => import('../views/Users.vue') },
    ]
  }
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
