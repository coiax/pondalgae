import pond

import pyglet
import pyglet.window
import pyglet.graphics
import pyglet.gl
import pyglet.app
import pyglet.clock


class PondWindow(pyglet.window.Window):
    def __init__(self, *args, **kwargs):
        super(PondWindow, self).__init__(*args, **kwargs)

        self.fpses = []

    def on_draw(self):
        X, Y = self.get_size()

        x = random.randint(0,X)
        y = random.randint(0,Y)

        colour = tuple(random.randint(0,255) for i in range(4))
        self._set_pixel((x,y), colour)

        self.fpses.append(pyglet.clock.get_fps())

    def _set_pixel(self, coord, colour):
        pyglet.graphics.draw(1, pyglet.gl.GL_POINTS,
                             ('v2i', coord),
                             ('c4B', colour))

if __name__=='__main__':
    pond = pond.Pond()
    window = PondWindow(width=pond.size[0], height=pond.size[1])
    pyglet.app.run()

    print sum(window.fpses) / float(len(window.fpses))
