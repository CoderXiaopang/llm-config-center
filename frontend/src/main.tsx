import React, { useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import { App as AntApp, Button, Card, Checkbox, ConfigProvider, Form, Input, InputNumber, Layout, Menu, Modal, Popconfirm, Select, Space, Statistic, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import zhCN from "antd/locale/zh_CN";
import { AppWindow, Boxes, ClipboardList, Database, FileKey, History, KeyRound, Layers, LayoutDashboard, LogOut, PlusCircle, ShieldCheck, SlidersHorizontal, UsersRound } from "lucide-react";
import { api, pickData } from "./api/client";
import "./styles.css";

type Entity = Record<string, any>;

const { Sider, Header, Content } = Layout;

const menuItems = [
  { key: "config-items", icon: <PlusCircle size={17} />, label: "配置项" },
  { key: "users", icon: <UsersRound size={17} />, label: "用户管理" }
];

const callTypeOptions = [
  { label: "文本对话", value: "chat" },
  { label: "Responses 多模态", value: "responses" },
  { label: "图片生成/编辑", value: "image" }
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
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [passwordForm] = Form.useForm();

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

  async function changePassword() {
    const values = await passwordForm.validateFields();
    if (values.new_password !== values.confirm_password) {
      message.error("两次输入的新密码不一致");
      return;
    }
    try {
      await api.post("/auth/password", {
        old_password: values.old_password,
        new_password: values.new_password
      });
      message.success("密码已修改，请重新登录");
      setPasswordOpen(false);
      passwordForm.resetFields();
      localStorage.removeItem("admin_token");
      localStorage.removeItem("admin_user");
      location.href = "/login";
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      message.error(detail === "OLD_PASSWORD_INVALID" ? "旧密码不正确" : "修改失败");
    }
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
            <span>一处维护客户端初始化需要的模型配置</span>
          </div>
          <Space>
            <Tag color="cyan">{user}</Tag>
            <Button onClick={() => setPasswordOpen(true)}>修改密码</Button>
            <Button icon={<LogOut size={16} />} onClick={logout}>
              退出登录
            </Button>
          </Space>
        </Header>
        <Content className="content">{renderPage(page)}</Content>
      </Layout>
      <Modal title="修改密码" open={passwordOpen} onOk={changePassword} onCancel={() => setPasswordOpen(false)} okText="保存" cancelText="取消">
        <Form form={passwordForm} layout="vertical">
          <Form.Item label="旧密码" name="old_password" rules={[{ required: true, message: "请输入旧密码" }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item label="新密码" name="new_password" rules={[{ required: true, message: "请输入新密码" }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item label="确认新密码" name="confirm_password" rules={[{ required: true, message: "请再次输入新密码" }]}>
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
}

function renderPage(page: string) {
  if (page === "config-items") return <ConfigItemPage />;
  if (page === "users") return <UserPage />;
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

function UserPage() {
  const [rows, setRows] = useState<Entity[]>([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Entity | null>(null);
  const [resetting, setResetting] = useState<Entity | null>(null);
  const [form] = Form.useForm();
  const [resetForm] = Form.useForm();

  async function load() {
    setRows(pickData<Entity[]>(await api.get("/users")));
  }

  useEffect(() => {
    load();
  }, []);

  function startCreate() {
    setEditing(null);
    form.setFieldsValue({ role: "admin", status: "enabled" });
    setOpen(true);
  }

  function startEdit(row: Entity) {
    setEditing(row);
    form.setFieldsValue({
      username: row.username,
      display_name: row.display_name,
      role: row.role,
      status: row.status
    });
    setOpen(true);
  }

  async function saveUser() {
    const values = await form.validateFields();
    try {
      if (editing) {
        await api.put(`/users/${editing.id}`, {
          username: values.username,
          display_name: values.display_name,
          role: values.role,
          status: values.status
        });
        message.success("用户已更新");
      } else {
        await api.post("/users", values);
        message.success("用户已创建");
      }
      setOpen(false);
      setEditing(null);
      form.resetFields();
      load();
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      message.error(detail === "USERNAME_EXISTS" ? "用户名已存在" : "保存失败");
    }
  }

  async function toggleUser(row: Entity) {
    const action = row.status === "enabled" ? "disable" : "enable";
    await api.post(`/users/${row.id}/${action}`);
    message.success(row.status === "enabled" ? "用户已禁用" : "用户已启用");
    load();
  }

  async function resetPassword() {
    if (!resetting) return;
    const values = await resetForm.validateFields();
    await api.post(`/users/${resetting.id}/password`, { password: values.password });
    message.success("密码已重置");
    setResetting(null);
    resetForm.resetFields();
  }

  return (
    <Card title="用户管理" extra={<Button type="primary" onClick={startCreate}>新增用户</Button>}>
      <Table
        rowKey="id"
        dataSource={rows}
        pagination={{ pageSize: 10 }}
        columns={[
          { title: "ID", dataIndex: "id", width: 70 },
          { title: "用户名", dataIndex: "username" },
          { title: "显示名称", dataIndex: "display_name" },
          { title: "角色", dataIndex: "role", width: 130 },
          { title: "状态", dataIndex: "status", render: statusTag, width: 90 },
          { title: "最近登录", dataIndex: "last_login_at" },
          {
            title: "操作",
            width: 260,
            render: (_, row) => (
              <Space>
                <Button size="small" onClick={() => startEdit(row)}>编辑</Button>
                <Button size="small" onClick={() => setResetting(row)}>重置密码</Button>
                <Popconfirm title={`确认${row.status === "enabled" ? "禁用" : "启用"}该用户？`} okText="确认" cancelText="取消" onConfirm={() => toggleUser(row)}>
                  <Button size="small" danger={row.status === "enabled"}>{row.status === "enabled" ? "禁用" : "启用"}</Button>
                </Popconfirm>
              </Space>
            )
          }
        ]}
      />
      <Modal title={editing ? "编辑用户" : "新增用户"} open={open} onOk={saveUser} onCancel={() => setOpen(false)} okText="保存" cancelText="取消" width={620}>
        <Form form={form} layout="vertical">
          <Form.Item label="用户名" name="username" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input placeholder="例如 zhangsan" />
          </Form.Item>
          <Form.Item label="显示名称" name="display_name">
            <Input placeholder="例如 张三" />
          </Form.Item>
          <div className="form-grid">
            <Form.Item label="角色" name="role" rules={[{ required: true, message: "请选择角色" }]}>
              <Select options={[
                { label: "管理员", value: "admin" },
                { label: "超级管理员", value: "super_admin" },
                { label: "查看者", value: "viewer" },
                { label: "操作员", value: "operator" }
              ]} />
            </Form.Item>
            <Form.Item label="状态" name="status" rules={[{ required: true, message: "请选择状态" }]}>
              <Select options={[{ label: "启用", value: "enabled" }, { label: "禁用", value: "disabled" }]} />
            </Form.Item>
          </div>
          {!editing && (
            <Form.Item label="密码" name="password" rules={[{ required: true, message: "请输入密码" }]}>
              <Input.Password placeholder="请输入初始密码" />
            </Form.Item>
          )}
        </Form>
      </Modal>
      <Modal title={`重置密码：${resetting?.username || ""}`} open={Boolean(resetting)} onOk={resetPassword} onCancel={() => setResetting(null)} okText="保存" cancelText="取消">
        <Form form={resetForm} layout="vertical">
          <Form.Item label="新密码" name="password" rules={[{ required: true, message: "请输入新密码" }]}>
            <Input.Password placeholder="请输入新密码" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}

function ConfigItemPage() {
  const [rows, setRows] = useState<Entity[]>([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Entity | null>(null);
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
          <Button onClick={() => copyText(data.access_key)} disabled={!data.access_key}>复制访问密钥</Button>
          <Typography.Text>Python SDK 示例：</Typography.Text>
          <Input.TextArea value={data.sdk_example || ""} rows={8} readOnly />
        </Space>
      )
    });
  }

  function fallbackCopyText(text: string) {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    textarea.style.top = "0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const copied = document.execCommand("copy");
    document.body.removeChild(textarea);
    if (!copied) {
      throw new Error("复制失败");
    }
  }

  async function copyText(text?: string) {
    if (!text) {
      message.warning("这个历史密钥没有保存明文，请编辑配置项后重新生成");
      return;
    }
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        fallbackCopyText(text);
      }
      message.success("已复制访问密钥");
    } catch {
      message.error("复制失败，请手动选中访问密钥复制");
    }
  }

  async function saveItem() {
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
      create_access_key: Boolean(raw.create_access_key),
      status: "enabled"
    };
    try {
      const response = editing ? await api.put(`/config-items/${editing.id}`, payload) : await api.post("/config-items", { ...payload, create_access_key: true });
      const data = pickData<Entity>(response);
      message.success(editing ? "配置项已更新" : "配置项已创建");
      setOpen(false);
      setEditing(null);
      form.resetFields();
      if (data.access_key) {
        showResult(data);
      }
      load();
    } catch (error: any) {
      message.error(error.response?.data?.message || "创建失败");
    }
  }

  function startCreate() {
    setEditing(null);
    form.setFieldsValue({
      env: "prod",
      provider_code: "openai",
      provider_name: "OpenAI Compatible",
      model_type: "chat",
      call_type: "chat",
      app_code: "default-client",
      app_name: "默认客户端",
      access_key_name: "默认访问密钥",
      create_access_key: true,
      default_params: JSON.stringify({ temperature: 0.7, max_tokens: 4096, timeout: 60, stream: true }, null, 2)
    });
    setOpen(true);
  }

  function startEdit(row: Entity) {
    setEditing(row);
    form.setFieldsValue({
      alias: row.alias,
      env: row.env,
      provider_code: row.provider_code,
      provider_name: row.provider_name,
      base_url: row.base_url,
      model_name: row.model_name,
      model_type: row.model_type,
      call_type: row.call_type || "chat",
      api_key: undefined,
      default_params: JSON.stringify(row.params || {}, null, 2),
      app_code: row.app_code || "default-client",
      app_name: row.app_code || "默认客户端",
      access_key_name: `${row.alias || "default"}-key`,
      create_access_key: false
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
          { title: "调用类型", dataIndex: "call_type", width: 130, render: (value) => callTypeOptions.find((item) => item.value === value)?.label || value },
          { title: "Base URL", dataIndex: "base_url", ellipsis: true },
          {
            title: "访问密钥",
            dataIndex: "access_key",
            width: 260,
            render: (value) => (
              <Space>
                <Typography.Text code className="secret-cell">{value || "历史密钥不可显示"}</Typography.Text>
                <Button size="small" onClick={() => copyText(value)}>复制</Button>
              </Space>
            )
          },
          { title: "版本", dataIndex: "version", width: 80 },
          { title: "状态", dataIndex: "status", render: statusTag, width: 90 },
          { title: "操作", width: 90, render: (_, row) => <Button size="small" onClick={() => startEdit(row)}>编辑</Button> }
        ]}
      />
      <Modal title={editing ? "编辑配置项" : "新增配置项"} open={open} onOk={saveItem} onCancel={() => setOpen(false)} okText={editing ? "保存修改" : "创建配置项"} cancelText="取消" width={760}>
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
            <Form.Item label="调用类型" name="call_type" rules={[{ required: true, message: "请选择调用类型" }]}>
              <Select options={callTypeOptions} />
            </Form.Item>
          </div>
          <Form.Item label="上游 API Key" name="api_key" rules={[{ required: !editing, message: "请输入上游 API Key" }]}>
            <Input.Password placeholder={editing ? "不填则保留原来的上游 API Key" : "这里填真实模型供应商的 API Key"} />
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
          {editing && (
            <Form.Item name="create_access_key" valuePropName="checked">
              <Checkbox>重新生成并保存新的访问密钥</Checkbox>
            </Form.Item>
          )}
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
