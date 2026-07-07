import React, { useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import { App as AntApp, Button, Card, ConfigProvider, Form, Input, InputNumber, Layout, Menu, Modal, Popconfirm, Select, Space, Statistic, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import zhCN from "antd/locale/zh_CN";
import { AppWindow, Boxes, ClipboardList, Database, FileKey, History, KeyRound, Layers, LayoutDashboard, LogOut, PlusCircle, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { api, pickData } from "./api/client";
import "./styles.css";

type Entity = Record<string, any>;

const { Sider, Header, Content } = Layout;

const menuItems = [
  { key: "config-items", icon: <PlusCircle size={17} />, label: "配置项" },
  { key: "dashboard", icon: <LayoutDashboard size={17} />, label: "总览" },
  { key: "providers", icon: <Database size={17} />, label: "供应商管理" },
  { key: "provider-api-keys", icon: <KeyRound size={17} />, label: "上游 API Key" },
  { key: "models", icon: <Boxes size={17} />, label: "模型管理" },
  { key: "aliases", icon: <SlidersHorizontal size={17} />, label: "模型别名" },
  { key: "apps", icon: <AppWindow size={17} />, label: "应用管理" },
  { key: "access-keys", icon: <FileKey size={17} />, label: "访问密钥" },
  { key: "permissions", icon: <ShieldCheck size={17} />, label: "权限管理" },
  { key: "audit-logs", icon: <History size={17} />, label: "审计日志" }
];

function statusTag(status?: string) {
  return <Tag color={status === "enabled" ? "green" : "red"}>{status === "enabled" ? "启用" : "禁用"}</Tag>;
}

function LoginPage() {
  const [loading, setLoading] = useState(false);

  async function onFinish(values: Entity) {
    setLoading(true);
    try {
      const data = pickData<any>(await api.post("/auth/login", values));
      localStorage.setItem("admin_token", data.access_token);
      localStorage.setItem("admin_user", data.user.display_name || data.user.username);
      location.href = "/";
    } catch {
      message.error("登录失败，请检查用户名和密码");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <section className="login-panel">
        <div className="brand-mark">LC</div>
        <Typography.Title level={2}>大模型配置中心</Typography.Title>
        <Typography.Paragraph>统一维护供应商、模型别名、访问密钥和应用权限。</Typography.Paragraph>
        <Form layout="vertical" onFinish={onFinish} initialValues={{ username: "admin", password: "admin123456" }}>
          <Form.Item label="用户名" name="username" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input size="large" placeholder="请输入用户名" />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password size="large" placeholder="请输入密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" size="large" loading={loading} block>
            登录后台
          </Button>
        </Form>
      </section>
    </div>
  );
}

function AppShell() {
  const savedPage = localStorage.getItem("current_page") || "config-items";
  const [page, setPage] = useState(menuItems.some((item) => item.key === savedPage) ? savedPage : "config-items");
  const user = localStorage.getItem("admin_user") || "管理员";

  useEffect(() => {
    if (!localStorage.getItem("admin_token")) {
      location.href = "/login";
    }
  }, []);

  function switchPage(key: string) {
    setPage(key);
    localStorage.setItem("current_page", key);
  }

  function logout() {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_user");
    location.href = "/login";
  }

  return (
    <Layout className="app-shell">
      <Sider width={232} className="sidebar">
        <div className="side-brand">
          <div className="brand-mark small">LC</div>
          <div>
            <strong>大模型配置中心</strong>
            <span>内部配置管理</span>
          </div>
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={[page]} items={menuItems} onClick={(item) => switchPage(item.key)} />
      </Sider>
      <Layout>
        <Header className="topbar">
          <div>
            <Typography.Title level={4}>{menuItems.find((item) => item.key === page)?.label || "总览"}</Typography.Title>
            <span>维护 Runtime API 可下发的模型配置</span>
          </div>
          <Space>
            <Tag color="cyan">{user}</Tag>
            <Button icon={<LogOut size={16} />} onClick={logout}>
              退出登录
            </Button>
          </Space>
        </Header>
        <Content className="content">{renderPage(page)}</Content>
      </Layout>
    </Layout>
  );
}

function renderPage(page: string) {
  if (page === "config-items") return <ConfigItemPage />;
  if (page === "dashboard") return <Dashboard />;
  if (page === "providers") return <ProviderPage />;
  if (page === "provider-api-keys") return <ProviderKeyPage />;
  if (page === "models") return <ModelPage />;
  if (page === "aliases") return <AliasPage />;
  if (page === "apps") return <AppPage />;
  if (page === "access-keys") return <AccessKeyPage />;
  if (page === "permissions") return <PermissionPage />;
  return <AuditPage />;
}

function ConfigItemPage() {
  const [rows, setRows] = useState<Entity[]>([]);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  async function load() {
    setRows(pickData<Entity[]>(await api.get("/config-items")));
  }

  useEffect(() => {
    load();
  }, []);

  function showResult(data: Entity) {
    Modal.success({
      title: "配置项已创建，可以直接给客户端使用",
      width: 760,
      okText: "我已保存",
      content: (
        <Space direction="vertical" className="full" size={12}>
          <Typography.Text>客户端只需要下面三个值：</Typography.Text>
          <Input addonBefore="Alias" value={data.alias} readOnly />
          <Input addonBefore="环境" value={data.env} readOnly />
          <Input.TextArea value={data.access_key || "本次未创建新的 Access Key"} rows={3} readOnly />
          <Typography.Text>Python SDK 示例：</Typography.Text>
          <Input.TextArea value={data.sdk_example || ""} rows={8} readOnly />
        </Space>
      )
    });
  }

  async function createItem() {
    const raw = await form.validateFields();
    let params = {};
    try {
      params = raw.default_params ? JSON.parse(raw.default_params) : {};
    } catch {
      message.error("默认参数 JSON 格式不正确");
      return;
    }

    const payload = {
      ...raw,
      default_params: params,
      create_access_key: true,
      status: "enabled"
    };
    try {
      const data = pickData<Entity>(await api.post("/config-items", payload));
      message.success("配置项已创建");
      setOpen(false);
      form.resetFields();
      showResult(data);
      load();
    } catch (error: any) {
      message.error(error.response?.data?.message || "创建失败");
    }
  }

  function startCreate() {
    form.setFieldsValue({
      env: "prod",
      provider_code: "openai",
      provider_name: "OpenAI Compatible",
      model_type: "chat",
      app_code: "default-client",
      app_name: "默认客户端",
      access_key_name: "默认访问密钥",
      default_params: JSON.stringify({ temperature: 0.7, max_tokens: 4096, timeout: 60, stream: true }, null, 2)
    });
    setOpen(true);
  }

  return (
    <Card
      title="配置项"
      extra={<Button type="primary" icon={<PlusCircle size={16} />} onClick={startCreate}>新增配置项</Button>}
    >
      <Typography.Paragraph className="page-hint">
        这里是最简单的入口：一次填完客户端初始化需要的 Alias、Base URL、模型名、API Key 和默认参数。系统会自动处理供应商、模型、权限和访问密钥。
      </Typography.Paragraph>
      <Table
        rowKey="id"
        dataSource={rows}
        pagination={{ pageSize: 10 }}
        columns={[
          { title: "Alias", dataIndex: "alias" },
          { title: "环境", dataIndex: "env", width: 90 },
          { title: "供应商", dataIndex: "provider_name" },
          { title: "模型", dataIndex: "model_name" },
          { title: "Base URL", dataIndex: "base_url", ellipsis: true },
          { title: "Key", dataIndex: "key_mask" },
          { title: "客户端", dataIndex: "app_code" },
          { title: "版本", dataIndex: "version", width: 80 },
          { title: "状态", dataIndex: "status", render: statusTag, width: 90 }
        ]}
      />
      <Modal title="新增配置项" open={open} onOk={createItem} onCancel={() => setOpen(false)} okText="创建配置项" cancelText="取消" width={760}>
        <Form form={form} layout="vertical">
          <div className="form-grid">
            <Form.Item label="Alias（业务代码使用的名称）" name="alias" rules={[{ required: true, message: "请输入 Alias" }]}>
              <Input placeholder="例如 chat-default" />
            </Form.Item>
            <Form.Item label="环境" name="env" rules={[{ required: true, message: "请输入环境" }]}>
              <Input placeholder="prod" />
            </Form.Item>
            <Form.Item label="供应商编码" name="provider_code" rules={[{ required: true, message: "请输入供应商编码" }]}>
              <Input placeholder="例如 volcengine / dashscope / openai" />
            </Form.Item>
            <Form.Item label="供应商名称" name="provider_name" rules={[{ required: true, message: "请输入供应商名称" }]}>
              <Input placeholder="例如 火山引擎" />
            </Form.Item>
          </div>
          <Form.Item label="Base URL" name="base_url" rules={[{ required: true, message: "请输入 Base URL" }]}>
            <Input placeholder="例如 https://ark.cn-beijing.volces.com/api/v3" />
          </Form.Item>
          <div className="form-grid">
            <Form.Item label="真实模型名" name="model_name" rules={[{ required: true, message: "请输入真实模型名" }]}>
              <Input placeholder="例如 doubao-seed-1.6 / qwen-plus" />
            </Form.Item>
            <Form.Item label="模型类型" name="model_type" rules={[{ required: true, message: "请选择模型类型" }]}>
              <Select options={["chat", "vision", "embedding", "rerank", "image", "audio"].map((value) => ({ label: value, value }))} />
            </Form.Item>
          </div>
          <Form.Item label="上游 API Key" name="api_key" rules={[{ required: true, message: "请输入上游 API Key" }]}>
            <Input.Password placeholder="这里填真实模型供应商的 API Key，数据库会加密保存" />
          </Form.Item>
          <Form.Item label="默认参数 JSON" name="default_params">
            <Input.TextArea rows={6} />
          </Form.Item>
          <div className="form-grid">
            <Form.Item label="客户端编码" name="app_code" rules={[{ required: true, message: "请输入客户端编码" }]}>
              <Input placeholder="例如 requirement-api" />
            </Form.Item>
            <Form.Item label="客户端名称" name="app_name" rules={[{ required: true, message: "请输入客户端名称" }]}>
              <Input placeholder="例如 需求提取服务" />
            </Form.Item>
          </div>
          <Form.Item label="访问密钥名称" name="access_key_name" rules={[{ required: true, message: "请输入访问密钥名称" }]}>
            <Input placeholder="例如 requirement-api-prod-key" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}

function Dashboard() {
  const [stats, setStats] = useState<Entity>({});
  const [logs, setLogs] = useState<Entity[]>([]);

  useEffect(() => {
    api.get("/dashboard").then((res) => setStats(pickData(res)));
    api.get("/audit-logs").then((res) => setLogs(pickData<any>(res).items));
  }, []);

  const cards = [
    ["供应商", stats.providers, <Database size={20} />],
    ["模型", stats.models, <Boxes size={20} />],
    ["别名", stats.aliases, <Layers size={20} />],
    ["应用", stats.apps, <AppWindow size={20} />],
    ["访问密钥", stats.access_keys, <FileKey size={20} />],
    ["配置版本", stats.config_version, <ClipboardList size={20} />]
  ];

  return (
    <Space direction="vertical" size={16} className="full">
      <div className="dashboard-grid">
        <section className="dashboard-main">
          <div className="stat-grid">
            {cards.map(([title, value, icon]) => (
              <Card key={String(title)}>
                <div className="stat-icon">{icon}</div>
                <Statistic title={title as string} value={(value as number) ?? 0} />
              </Card>
            ))}
          </div>
        </section>
        <Card title="运行时配置预览" className="runtime-preview" extra={<Button size="small">复制</Button>}>
          <pre>{JSON.stringify({
            env: "prod",
            version: stats.config_version ?? 1,
            providers: [],
            aliases: [],
            apps: []
          }, null, 2)}</pre>
        </Card>
      </div>
      <Card title="最近审计记录" extra={<ClipboardList size={18} />}>
        <Table rowKey="id" dataSource={logs} pagination={{ pageSize: 8 }} columns={[
          { title: "动作", dataIndex: "action" },
          { title: "资源类型", dataIndex: "resource_type" },
          { title: "资源 ID", dataIndex: "resource_id" },
          { title: "时间", dataIndex: "created_at" }
        ]} />
      </Card>
    </Space>
  );
}

type FieldSpec = {
  name: string;
  label: string;
  type?: "text" | "number" | "select" | "textarea" | "json" | "password";
  options?: { label: string; value: any }[];
  required?: boolean;
};

function ResourcePage({
  title,
  endpoint,
  fields,
  columns,
  normalize,
  afterCreate
}: {
  title: string;
  endpoint: string;
  fields: FieldSpec[];
  columns: ColumnsType<Entity>;
  normalize?: (values: Entity) => Entity;
  afterCreate?: (data: Entity) => void;
}) {
  const [rows, setRows] = useState<Entity[]>([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Entity | null>(null);
  const [form] = Form.useForm();

  async function load() {
    setRows(pickData<Entity[]>(await api.get(endpoint)));
  }

  useEffect(() => {
    load();
  }, [endpoint]);

  async function save() {
    const raw = await form.validateFields();
    const values = normalize ? normalize(raw) : raw;
    try {
      const response = editing ? await api.put(`${endpoint}/${editing.id}`, values) : await api.post(endpoint, values);
      message.success(editing ? "已保存修改" : "已创建");
      setOpen(false);
      setEditing(null);
      form.resetFields();
      afterCreate?.(pickData(response));
      load();
    } catch (error: any) {
      message.error(error.response?.data?.message || "保存失败");
    }
  }

  function startCreate() {
    setEditing(null);
    form.resetFields();
    setOpen(true);
  }

  function startEdit(row: Entity) {
    setEditing(row);
    form.setFieldsValue({ ...row, default_params: row.default_params ? JSON.stringify(row.default_params, null, 2) : undefined });
    setOpen(true);
  }

  return (
    <Card title={title} extra={<Button type="primary" onClick={startCreate}>新增</Button>}>
      <Table
        rowKey="id"
        dataSource={rows}
        pagination={{ pageSize: 10 }}
        columns={[
          ...columns,
          {
            title: "操作",
            width: 150,
            render: (_, row) => (
              <Space>
                <Button size="small" onClick={() => startEdit(row)}>编辑</Button>
                {"status" in row && <ToggleButton endpoint={endpoint} row={row} onDone={load} />}
              </Space>
            )
          }
        ]}
      />
      <Modal title={editing ? `编辑${title}` : `新增${title}`} open={open} onOk={save} onCancel={() => setOpen(false)} okText="保存" cancelText="取消" width={680}>
        <Form form={form} layout="vertical">
          {fields.map((field) => (
            <Form.Item key={field.name} label={field.label} name={field.name} rules={[{ required: field.required !== false, message: `请输入${field.label}` }]}>
              {renderField(field)}
            </Form.Item>
          ))}
        </Form>
      </Modal>
    </Card>
  );
}

function renderField(field: FieldSpec) {
  if (field.type === "number") return <InputNumber className="full" />;
  if (field.type === "select") return <Select options={field.options} />;
  if (field.type === "textarea" || field.type === "json") return <Input.TextArea rows={field.type === "json" ? 7 : 3} />;
  if (field.type === "password") return <Input.Password />;
  return <Input />;
}

function ToggleButton({ endpoint, row, onDone }: { endpoint: string; row: Entity; onDone: () => void }) {
  const action = row.status === "enabled" ? "disable" : "enable";
  const label = row.status === "enabled" ? "禁用" : "启用";
  return (
    <Popconfirm title={`确认${label}？`} okText="确认" cancelText="取消" onConfirm={async () => {
      await api.post(`${endpoint}/${row.id}/${action}`);
      message.success(`已${label}`);
      onDone();
    }}>
      <Button size="small" danger={row.status === "enabled"}>{label}</Button>
    </Popconfirm>
  );
}

function ProviderPage() {
  return (
    <ResourcePage
      title="供应商"
      endpoint="/providers"
      fields={[
        { name: "code", label: "供应商编码" },
        { name: "name", label: "供应商名称" },
        { name: "protocol", label: "协议", required: false },
        { name: "base_url", label: "Base URL" },
        { name: "status", label: "状态", type: "select", options: [{ label: "启用", value: "enabled" }, { label: "禁用", value: "disabled" }] },
        { name: "description", label: "描述", type: "textarea", required: false }
      ]}
      columns={[
        { title: "ID", dataIndex: "id", width: 70 },
        { title: "编码", dataIndex: "code" },
        { title: "名称", dataIndex: "name" },
        { title: "协议", dataIndex: "protocol" },
        { title: "Base URL", dataIndex: "base_url", ellipsis: true },
        { title: "状态", dataIndex: "status", render: statusTag }
      ]}
    />
  );
}

function ProviderKeyPage() {
  return (
    <ResourcePage
      title="上游 API Key"
      endpoint="/provider-api-keys"
      fields={[
        { name: "provider_id", label: "供应商 ID", type: "number" },
        { name: "name", label: "Key 名称" },
        { name: "api_key", label: "明文 API Key", type: "password", required: false },
        { name: "status", label: "状态", type: "select", options: [{ label: "启用", value: "enabled" }, { label: "禁用", value: "disabled" }] },
        { name: "priority", label: "优先级", type: "number", required: false }
      ]}
      columns={[
        { title: "ID", dataIndex: "id", width: 70 },
        { title: "供应商 ID", dataIndex: "provider_id" },
        { title: "名称", dataIndex: "name" },
        { title: "Key 脱敏值", dataIndex: "key_mask" },
        { title: "状态", dataIndex: "status", render: statusTag },
        { title: "优先级", dataIndex: "priority" }
      ]}
    />
  );
}

function ModelPage() {
  return (
    <ResourcePage
      title="模型"
      endpoint="/models"
      fields={[
        { name: "provider_id", label: "供应商 ID", type: "number" },
        { name: "model_name", label: "真实模型名" },
        { name: "display_name", label: "显示名称", required: false },
        { name: "model_type", label: "模型类型", type: "select", options: ["chat", "vision", "embedding", "rerank", "image", "audio"].map((v) => ({ label: v, value: v })) },
        { name: "context_window", label: "上下文窗口", type: "number", required: false },
        { name: "max_output_tokens", label: "最大输出 Token", type: "number", required: false },
        { name: "status", label: "状态", type: "select", options: [{ label: "启用", value: "enabled" }, { label: "禁用", value: "disabled" }] }
      ]}
      columns={[
        { title: "ID", dataIndex: "id", width: 70 },
        { title: "供应商 ID", dataIndex: "provider_id" },
        { title: "模型名", dataIndex: "model_name" },
        { title: "类型", dataIndex: "model_type" },
        { title: "状态", dataIndex: "status", render: statusTag }
      ]}
    />
  );
}

function AliasPage() {
  return (
    <ResourcePage
      title="模型别名"
      endpoint="/aliases"
      normalize={(values) => ({ ...values, default_params: values.default_params ? JSON.parse(values.default_params) : {} })}
      fields={[
        { name: "alias", label: "Alias" },
        { name: "env", label: "环境" },
        { name: "model_id", label: "模型 ID", type: "number" },
        { name: "provider_api_key_id", label: "上游 API Key ID", type: "number" },
        { name: "default_params", label: "默认参数 JSON", type: "json", required: false },
        { name: "status", label: "状态", type: "select", options: [{ label: "启用", value: "enabled" }, { label: "禁用", value: "disabled" }] },
        { name: "description", label: "描述", type: "textarea", required: false }
      ]}
      columns={[
        { title: "ID", dataIndex: "id", width: 70 },
        { title: "Alias", dataIndex: "alias" },
        { title: "环境", dataIndex: "env" },
        { title: "模型 ID", dataIndex: "model_id" },
        { title: "Key ID", dataIndex: "provider_api_key_id" },
        { title: "版本", dataIndex: "version" },
        { title: "状态", dataIndex: "status", render: statusTag }
      ]}
    />
  );
}

function AppPage() {
  return (
    <ResourcePage
      title="应用"
      endpoint="/apps"
      fields={[
        { name: "app_code", label: "应用编码" },
        { name: "app_name", label: "应用名称" },
        { name: "owner", label: "负责人", required: false },
        { name: "status", label: "状态", type: "select", options: [{ label: "启用", value: "enabled" }, { label: "禁用", value: "disabled" }] },
        { name: "description", label: "描述", type: "textarea", required: false }
      ]}
      columns={[
        { title: "ID", dataIndex: "id", width: 70 },
        { title: "应用编码", dataIndex: "app_code" },
        { title: "应用名称", dataIndex: "app_name" },
        { title: "负责人", dataIndex: "owner" },
        { title: "状态", dataIndex: "status", render: statusTag }
      ]}
    />
  );
}

function AccessKeyPage() {
  const [appId, setAppId] = useState<number | null>(null);
  const [rows, setRows] = useState<Entity[]>([]);
  const [name, setName] = useState("");

  async function load(id = appId) {
    if (!id) return;
    setRows(pickData(await api.get(`/apps/${id}/access-keys`)));
  }

  async function createKey() {
    if (!appId || !name) {
      message.warning("请填写应用 ID 和密钥名称");
      return;
    }
    const data = pickData<Entity>(await api.post(`/apps/${appId}/access-keys`, { name }));
    Modal.info({
      title: "请立即保存访问密钥",
      width: 680,
      content: <Input.TextArea value={data.access_key} rows={3} readOnly />,
      okText: "我已保存"
    });
    setName("");
    load(appId);
  }

  return (
    <Card title="访问密钥">
      <Space className="toolbar">
        <InputNumber placeholder="应用 ID" value={appId} onChange={(value) => setAppId(value as number)} />
        <Input placeholder="密钥名称" value={name} onChange={(event) => setName(event.target.value)} />
        <Button type="primary" onClick={createKey}>创建密钥</Button>
        <Button onClick={() => load()}>查询</Button>
      </Space>
      <Table rowKey="id" dataSource={rows} columns={[
        { title: "ID", dataIndex: "id" },
        { title: "名称", dataIndex: "name" },
        { title: "Prefix", dataIndex: "key_prefix" },
        { title: "脱敏值", dataIndex: "key_mask" },
        { title: "状态", dataIndex: "status", render: statusTag },
        { title: "最近使用时间", dataIndex: "last_used_at" }
      ]} />
    </Card>
  );
}

function PermissionPage() {
  const [appId, setAppId] = useState<number | null>(null);
  const [env, setEnv] = useState("prod");
  const [alias, setAlias] = useState("");
  const [rows, setRows] = useState<Entity[]>([]);

  async function load(id = appId) {
    if (!id) return;
    setRows(pickData(await api.get(`/apps/${id}/permissions`, { params: { env } })));
  }

  async function grant() {
    if (!appId || !alias) {
      message.warning("请填写应用 ID 和 Alias");
      return;
    }
    await api.post(`/apps/${appId}/permissions`, { alias, env, can_read_config: true });
    message.success("授权成功");
    setAlias("");
    load(appId);
  }

  async function remove(row: Entity) {
    await api.delete(`/apps/${appId}/permissions/${row.id}`);
    message.success("权限已删除");
    load(appId);
  }

  return (
    <Card title="权限管理">
      <Space className="toolbar">
        <InputNumber placeholder="应用 ID" value={appId} onChange={(value) => setAppId(value as number)} />
        <Input placeholder="环境" value={env} onChange={(event) => setEnv(event.target.value)} />
        <Input placeholder="Alias" value={alias} onChange={(event) => setAlias(event.target.value)} />
        <Button type="primary" onClick={grant}>授权 Alias</Button>
        <Button onClick={() => load()}>查询</Button>
      </Space>
      <Table rowKey="id" dataSource={rows} columns={[
        { title: "ID", dataIndex: "id" },
        { title: "应用 ID", dataIndex: "app_id" },
        { title: "环境", dataIndex: "env" },
        { title: "Alias", dataIndex: "alias" },
        { title: "可读配置", dataIndex: "can_read_config", render: (v) => (v ? "是" : "否") },
        { title: "操作", render: (_, row) => <Popconfirm title="确认删除权限？" okText="确认" cancelText="取消" onConfirm={() => remove(row)}><Button danger size="small">删除</Button></Popconfirm> }
      ]} />
    </Card>
  );
}

function AuditPage() {
  const [rows, setRows] = useState<Entity[]>([]);
  useEffect(() => {
    api.get("/audit-logs").then((res) => setRows(pickData<any>(res).items));
  }, []);
  return (
    <Card title="审计日志">
      <Table rowKey="id" dataSource={rows} columns={[
        { title: "ID", dataIndex: "id", width: 70 },
        { title: "用户 ID", dataIndex: "user_id" },
        { title: "动作", dataIndex: "action" },
        { title: "资源类型", dataIndex: "resource_type" },
        { title: "资源 ID", dataIndex: "resource_id" },
        { title: "时间", dataIndex: "created_at" }
      ]} />
    </Card>
  );
}

function Root() {
  const isLogin = location.pathname === "/login";
  const theme = useMemo(() => ({
    token: {
      colorPrimary: "#0f766e",
      borderRadius: 8,
      colorText: "#17202a",
      colorBgLayout: "#f5f7f8",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    }
  }), []);
  return (
    <ConfigProvider locale={zhCN} theme={theme}>
      <AntApp>{isLogin ? <LoginPage /> : <AppShell />}</AntApp>
    </ConfigProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<Root />);
