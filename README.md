# Upper and lower computers
## 上下位机


### 上位机

mainui2.3+handle2.2<br>
模式切换不会报错<br>

mainui2.4<br>
点击连接开始记录日志，点击取消保存日志，每次连接都有新的日志文件<br>
更正了目标跟踪期望航向角的计算方式<br>

mainui2.5+headingholdtask2_2+index2.html<br>
将Es与期望航向角的计算放到任务文件中，主程序只发送经纬度和罗盘信息<br>
修复轨迹绘制功能<br>

headingholdtask2_3<br>
修正航向保持的角度问题<br>
修正Es计算方式<br>

mainui2.6+headingholdtask2_4+index2.html<br>
加上了路径跟踪算法<br>

mainui2.7+index3.html<br>
优化路径跟踪模式，能够通过选点自动填充<br>

mainui2.8+新ui<br>
加了输入模式，能根据输入的值控制电机<br>

mainui2.9<br>
修复了遥控模式切换到其他模式后出现Lsend和Rsend异常的bug<br>

mainui2.10++headingholdtask2_5+新ui<br>
路径跟踪模式增加为多点路径跟踪，到终点时会停下来
路径跟踪到终点后增加了返程选项
优化了udp传输过程中的问题


### 下位机
mainui2.3
超过3s接收不到上位机信息把占空比改为7.5