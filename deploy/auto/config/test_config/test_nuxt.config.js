const file = require('./static/config.json')
const apiBaseUrl = file.apiBaseUrl || 'http://192.168.0.123:28888/api'

export default {
  // Disable server-side rendering: https://go.nuxtjs.dev/ssr-mode
  ssr: false,

  // Target: https://go.nuxtjs.dev/config-target
  target: 'static',

  // Global page headers: https://go.nuxtjs.dev/config-head
  head: {
    title: '华能集团大连电厂智慧大数据建模平台',
    meta: [
      { charset: 'utf-8' },
      { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      { hid: 'description', name: 'description', content: '' },
      { name: 'format-detection', content: 'telephone=no' }
    ],
    link: [
      // { rel: 'icon', type: 'image/x-icon', href: '/favicon.ico' }
      { rel: 'shortcut icon', type: 'image/x-icon', href: '/favicon.ico?v=2' }
    ]
  },

  // Global CSS: https://go.nuxtjs.dev/config-css
  css: [
  ],

  // 禁用顶部加载动画
  loading: false,

  // Plugins to run before rendering page: https://go.nuxtjs.dev/config-plugins
  plugins: [
    '@/plugins/antd-ui',
    '@/plugins/api',
    '@/plugins/axios',
    '@/plugins/tool',
    '@/plugins/websocket',
    '@/plugins/router'
  ],

  // Auto import components: https://go.nuxtjs.dev/config-components
  components: true,

  // Modules for dev and build (recommended): https://go.nuxtjs.dev/config-modules
  buildModules: [
  ],

  // Modules: https://go.nuxtjs.dev/config-modules
  modules: [
    // https://go.nuxtjs.dev/axios
    '@nuxtjs/axios',
    // https://go.nuxtjs.dev/pwa
    '@nuxtjs/pwa',
    // https://go.nuxtjs.dev/content
    '@nuxt/content'
  ],

  // Axios module configuration: https://go.nuxtjs.dev/config-axios
  axios: {
    // 外网访问
    // baseURL: 'http://106.55.173.219:27818/api'
    // baseURL: 'http://106.55.173.219:39001/api'
    //测试环境
    baseURL: 'https://powerai.chng.com.cn:4443/api'
    //生产环境 本地
    // baseURL: 'http://106.55.173.219:29104/api'
    //测试https
    // baseURL: 'https://powerai.chng.com.cn:29216/api'
    // 部署环境
    // baseURL: 'http://172.17.86.17:29001/api'
    // baseURL: apiBaseUrl
    // 局域网
    // baseURL: 'http://192.168.0.106:27818/api'
    // baseURL: 'http://192.168.0.123:28888/api'
    // baseURL: 'http://192.168.0.106:29001/api'
    // baseURL: 'http://192.168.0.103:22222/api'
    // baseURL: 'http://192.168.0.101:22222/api'
  },

  // PWA module configuration: https://go.nuxtjs.dev/pwa
  pwa: {
    manifest: {
      lang: 'zh'
    }
  },

  // Content module configuration: https://go.nuxtjs.dev/config-content
  content: {},

  // Build Configuration: https://go.nuxtjs.dev/config-build
  build: {
  }
}
