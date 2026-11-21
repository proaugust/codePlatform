import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/books' },
    {
      path: '/books',
      name: 'book-list',
      component: () => import('../views/BookListView.vue')
    },
    {
      path: '/books/new',
      name: 'book-create',
      component: () => import('../views/BookCreateView.vue')
    },
    {
      path: '/books/:id',
      name: 'book-detail',
      component: () => import('../views/BookDetailView.vue'),
      props: true
    },
    { path: '/:pathMatch(.*)*', redirect: '/books' }
  ]
})

export default router
