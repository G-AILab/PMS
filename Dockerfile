# 使用 ubuntu:20.04 作为基础镜像
FROM ubuntu:20.04

# 设置工作目录
WORKDIR /workspace
# 拷贝当前目录下的文件到容器中的工作目录
COPY . /workspace
# 安装 openssh-server、vim、python3.8、pip 和其他依赖
RUN chmod 1777 /tmp  && sed -i 's/http:\/\/archive.ubuntu.com\/ubuntu\//http:\/\/mirrors.aliyun.com\/ubuntu\//g' /etc/apt/sources.list \
    && apt-get  update \
    && apt-get install -y  openssh-server vim python3.8 python3-pip  \
    && python3.8 -m pip install --upgrade pip \
    && echo "root:root"|chpasswd \
    && pip install -r requirements.txt -i https://pypi.mirrors.ustc.edu.cn/simple

# 开放端口 4399 和 18010
# 4399 用于api接口
# 18010 用于websocket
# 22 用于开发和测试版本的ssh连接，生产环境禁用
EXPOSE 22 4399 18010
#ENTRYPOINT ["./scripts/entry-point.sh"]
# 启动 ssh 服务
CMD ["/usr/sbin/sshd", "-D"]

