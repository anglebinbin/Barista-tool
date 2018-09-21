
# https://github.com/jupyter/qtconsole/blob/master/examples/inprocess_qtconsole.py
# https://stackoverflow.com/questions/26666583/embedding-ipython-qtconsole-and-passing-objects
import sys
qtconsole = True

if qtconsole:
    from qtconsole.qt import QtGui
    from qtconsole.rich_jupyter_widget import RichJupyterWidget
    from qtconsole.inprocess import QtInProcessKernelManager
    from ipykernel.inprocess import InProcessKernelManager
    def show(parent):
        global ipython_widget  # Prevent from being garbage collected

        # Create an in-process kernel
        kernel_manager = QtInProcessKernelManager()
        kernel_manager.start_kernel(show_banner=False)
        kernel = kernel_manager.kernel
        kernel.gui = 'qt'

        kernel_client = kernel_manager.client()
        kernel_client.start_channels()
        kernel_client.namespace = parent

        ipython_widget = RichJupyterWidget()
        ipython_widget.kernel_manager = kernel_manager
        ipython_widget.kernel_client = kernel_client
        ipython_widget.show()

        kernel.shell.push({"manager": parent})
else:
    from IPython.kernel.inprocess import InProcessKernelManager
    from IPython.terminal.console.interactiveshell import ZMQTerminalInteractiveShell

    #https://github.com/ipython/ipykernel/blob/master/examples/embedding/inprocess_terminal.py

    def show(parent):
        kernel_manager = InProcessKernelManager()
        kernel_manager.start_kernel()
        kernel = kernel_manager.kernel
        # kernel.gui = 'qt'
        kernel.shell.push({"manager": parent})
        client = kernel_manager.client()
        client.start_channels()

        shell = ZMQTerminalInteractiveShell(manager=kernel_manager, client=client)
        shell.mainloop()

