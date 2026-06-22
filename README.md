1 部署指南

本章主要讲解部署本系统的方法以及部署本系统所需要的所有前期准备，前期准备中重要性有大到小分别为Python环境准备、数据库准备、Redis准备、系统邮箱准备、数据集准备和大模型API准备，这些准备中缺少任何一个环节都无法准确、完整地部署运行本系统，下面将逐一介绍所有的准备工作以及本系统的运行方法。

1.1 Python环境准备

提交文件夹中的requiretments.txt文件中详细介绍了整个后端系统运行所需的第三方库及其版本，在运行本系统之前建议创建一个新的Python环境（Python版本建议为3.13.3）并按照此文件的内容下载第三方库，建议使用conda。该requiretments.txt文件的内容如下：
fastapi==0.135.1
uvicorn==0.46.0
Jinja2==3.1.6
pydantic==2.11.9
openpyxl==3.1.5
pyodbc==5.3.0
aioodbc==0.5.0
redis==6.4.0
PyJWT==2.12.1
bcrypt==5.0.0
openai==1.107.3
tqdm==4.67.1

1.2 数据库准备

本系统所依赖的数据库为SQL Server，版本为2025。我们在提交文件夹中已经包括了一个空数据库文件及其日志文件，在文件夹Database中，该数据库文件中所有表及其相关对象都已经创建完毕，但是每张表都是空的。在运行后端系统之前一定要确保本数据库已经在SQL Server中注册，最好的注册办法就是使用SQL Server Management Studio 22图形化工具提前将数据库文件附加。为了部署和测试方便，数据库连接方式暂时定位为localhost，身份验证方式暂时定为Windows身份验证。

1.3 Redis准备

在运行系统时需要Redis服务缓存一些数据，比如登录之后的身份令牌、验证码的有效期、学习用户每日单词学习信息缓存等。Redis的官方下载网址为https://redis.io/downloads/，我们在提交文件夹中也放入了它的安装程序，点击安装程序并按照相应指示安装即可，注意一定要将redis-server.exe程序添加到环境变量。

我们使用的Redis端口为localhost:6379，在运行Redis之前要确保所有有关redis://localhost:6379的进程关闭，具体做法是先在终端中输入netstat -ano | findstr :6379查看所有进程，如果没有任何输出信息则说明没有相关进程，否则会得到类似以下输出信息：
  TCP    0.0.0.0:6379       0.0.0.0:0           LISTENING      22640
  TCP    [::]:6379          [::]:0              LISTENING      22640
然后在管理员模式下打开终端，输入指令taskkill /F /PID 22640就可以关闭所有相关进程。然后在终端中输入redis-server.exe就可运行Redis，在运行后端系统之前一定要先启动Redis服务。如果控制台显示以下内容则说明成功运行了Redis：
[22640] 20 Jun 16:13:45.188 # oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
[22640] 20 Jun 16:13:45.188 # Redis version=5.0.14.1, bits=64, commit=ec77f72d, modified=0, pid=22640, just started
[22640] 20 Jun 16:13:45.188 # Warning: no config file specified, using the default config. In order to specify a config file use d:\program files\redis\redis-server.exe /path/to/redis.conf
                _._                                                  
           _.-``__ ''-._                                             
      _.-``    `.  `_.  ''-._           Redis 5.0.14.1 (ec77f72d/0) 64 bit
  .-`` .-```.  ```\/    _.,_ ''-._                                   
 (    '      ,       .-`  | `,    )     Running in standalone mode
 |`-._`-...-` __...-.``-._|'` _.-'|     Port: 6379
 |    `-._   `._    /     _.-'    |     PID: 22640
  `-._    `-._  `-./  _.-'    _.-'                                   
 |`-._`-._    `-.__.-'    _.-'_.-'|                                  
 |    `-._`-._        _.-'_.-'    |           http://redis.io        
  `-._    `-._`-.__.-'_.-'    _.-'                                   
 |`-._`-._    `-.__.-'    _.-'_.-'|                                  
 |    `-._`-._        _.-'_.-'    |                                  
  `-._    `-._`-.__.-'_.-'    _.-'                                   
      `-._    `-.__.-'    _.-'                                       
          `-._        _.-'                                           
              `-.__.-'                                               

[22640] 20 Jun 16:13:45.192 # Server initialized
[22640] 20 Jun 16:13:45.224 * DB loaded from disk: 0.036 seconds
[22640] 20 Jun 16:13:45.224 * Ready to accept connections

1.4 系统邮箱准备

由于我们的系统中有通过邮箱验证码注册和登录的业务，所以您必须准备一个邮箱负责发送这些验证码。需要将后端项目中constant.py文件中的以下配置改成您自己的邮箱：
email_config = {
    "EMAIL_HOST": '您自己邮箱的SMTP',
    "EMAIL_PORT": 您自己邮箱的PORT,
    "EMAIL_USER": '您自己的邮箱',
    "EMAIL_PWD": '您自己邮箱的PWD授权码'
}

1.5 数据集准备

尽管我们在提交文件夹中已经存放了已经预处理好的数据集json文件（注意现在的数据集只包括CET4的数据集用于测试，如果想要其它单词仓库完全可以另在github中寻找），但是我们的业务中存在学习用户在前端收听音频的功能，而数据库想要保存音频数据比较困难，则我们提供的json文件以及数据库表中的数据仅存储了音频文件在本人服务端电脑中的绝对路径，在前端用户需要收听音频时是先找到该音频路径然后再找到该音频文件并发送音频流而成的，显然相同的数据集在开发者和测试者电脑中的存放位置不尽相同，因此我们给出的json文件仅作为参考。我们CET4数据集的下载网址为：
https://github.com/ismartcoding/endict
将该仓库解压之后得到endict-main文件夹，该文件夹为该数据集的主文件夹，然后使用我们提供的代码就可以将该数据集处理为一个json文件，注意需要将后端项目中datasets文件下的constant.py文件中的endict_raw_path更改为刚才的数据集主文件夹的绝对路径，然后在后端项目的主函数中运行init_endict()函数即可在数据集主文件夹内得到相应的json文件，该json文件中音频绝对路径是测试者本地电脑中真实的绝对路径。此外，我们还提供了一个试卷数据集json文件，该json文件不存在上述的路径问题，可以直接使用，这两个json文件的具体使用方法将在测试指南中提到。

1.6 大模型API准备

在我们系统中的试卷评判模块中，其主观题我们采用调用线上大模型API来进行评判（这是我们系统的一个亮点，因为在展示时还没有团队实现这一功能），因此我们使用了硅基流动网站的大模型API，测试者需要登录其账号，然后充值（最多10元即可）以可以获取足够多的token，然后获取API秘钥，修改后端项目文件夹中的constant.py文件中的以下配置：
subject_evaluter_api_config = {
    "api_key": "将这串秘钥换成您自己的",
    "base_url": "https://api.siliconflow.cn/v1",
    "model": "deepseek-ai/DeepSeek-V3",
    "temperature": 0.1,
    "max_tokens": 1024,
    "stream": False 
}
已知硅基流动API获取网址为：
https://cloud.siliconflow.cn/me/account/ak

1.7 最终运行方法

切记确保完成以上所有准备流程后才运行后端代码，尤其是三个需要更改的配置（系统邮箱、数据集主文件夹以及线上大模型API秘钥）。确保数据库文件夹Database与后端项目Server Side的相对位置关系永远不变，否则可能会出现数据库连接的问题，尽管此时数据库已经在SQL Server中注册。在运行之前需要获取当前局域网的IPV4，因为测试时的路由基于服务端的局域网，在终端中输入指令ipconfig即可获取IPV4，我们的系统路由全部基于其5000端口。使用PyCharm或VS code打开后端项目文件夹Server Side（注意不是Server Side的上一级文件夹），找到后端项目文件夹中的main.py文件，这是整个后端系统的主程序，后端系统只能在该文件下运行，然后运行该main.py源程序即可，注意必须使用第1.1节创建的环境。在home.html文件和admin_home.html文件的JS中，API_BASE原本应该设为'http://IPV4:5000'以实现局域网内的所有客户端都能够连接服务端，但是为了测试者测试方便（不必因为局域网的变动就需要改变前端代码），该API_BASE被改为了'http://localhost:5000'，如果想要让其它设备也能连接服务端，那么必须改回'http://IPV4:5000'。在成功运行后端代码后，控制台会输出“管理员路由: df75d2aac0783622”，其中df75d2aac0783622表示管理员路由的隐藏网址，该内容被保存在admin_route.txt文件内，可以直接由管理员编辑。已知学习用户注册、登录和主页的网址分别为http://IPV4:5000/register、http://IPV4:5000/login、http://IPV4:5000/home，管理员的注册、登录和主页的网址分别为：http://IPV4:5000/df75d2aac0783622/register、http://IPV4:5000/df75d2aac0783622/login、http://IPV4:5000/df75d2aac0783622/home。如果运行后端系统后控制台出现以下字样内容就说明运行成功：
管理员路由: df75d2aac0783622
INFO:     Started server process [43648]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:5000 (Press CTRL+C to quit)
但在运行过程中难免不会出现运行时错误，我们已经做了异常处理，如果遇到了无法解决的问题可以通过邮箱brotron@qq.com联系张淏禹同学。此外，我们已经把所有的代码发布到了https://github.com/Disniason/ZGolvs仓库上，在提交后代码仍然可能会修改，可以通过该仓库获取最新的代码。
