A little lightbaking utility that generates a lightmap from baking an ambient occlusion and a shadow map of an object and then mixing those together with a normal mix using numpy for speed.

This may be buggy and still has some performance issues.


It also exports glTF's with custom glTF shaders (spec compliant) and slaps the baked lightmap on its as data.  


It stores any glTFs it has exported (for that session) along with the path, and it saves the images it has created.


TODO:

Needs to export incrementally and to version up as well for the exported glTFs, potentially adding metadata.

