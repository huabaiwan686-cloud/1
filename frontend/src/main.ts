import { createApp } from 'vue';
import Antd from 'ant-design-vue';
import 'ant-design-vue/dist/reset.css';
import './assets/global.css';
import './assets/theme.css';
import App from './App.vue';
import router from './router';

createApp(App).use(Antd).use(router).mount('#app');
