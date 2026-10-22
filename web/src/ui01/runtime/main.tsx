import { createRoot } from 'react-dom/client';
import { ConfigProvider } from 'antd';
import 'antd/dist/antd.css';
import '../editor.css';
import './runtime.css';
import WorkshopRuntime from './WorkshopRuntime';
const nonce = document.querySelector<HTMLMetaElement>('meta[name="style-nonce"]')?.content;
if (!nonce || nonce === '__STYLE_NONCE__') throw new Error('Secure runtime style nonce missing.');
createRoot(document.getElementById('root')!).render(<ConfigProvider csp={{ nonce }} theme={{ zeroRuntime: true }} wave={{ disabled: true }}><WorkshopRuntime /></ConfigProvider>);
