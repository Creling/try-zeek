title: The Export Statement
pcaps: 
pred: module
succ: log-factorial 

Writing a Module: Export
=========================

In this tutorial you will create a module that computes the factorial function (n!)
and writes the result to a log file.

As said before a module is a semantic entity. This means also that all variables and
functions that you want to use outside of that entity need to be made available.
In Bro this is done through an `export` block.

In the example here you see two bro files. One is the module-script factorial.bro, 
one is main.bro, the script that uses the module the resulting values. You can simply click on the 
tabs with the file names to switch between the bro-files.

Lets have a closer look on the code. 
The first line declares that this is a module named Factor.
We will come back to this later. 
The next thing is the export environment. Every record, variable, and function
that needs to be accessed from other scripts has to go here.
In this case the export environment contains a function declaration, 
expecting one parameter, returning one result value, both of type count.
Note that export values always have to be `global`. Otherwise they can't be used 
later.

The second part is the function implementation that simply computes the factorial of 
a given *n*.

Now switch tabs and looks at main.bro. The first line is the already 
known `load`-statement. This time it loads factorial.bro. 
Inside the event we define a vector of length 9, our *n*s that we will
give to the function as parameters.
Then we call iterate over the vector, calling the function and printing the result.
Note the syntax for calling the function. Before the function name we have to give the 
module name (Factor not factorial). Every time a parameter or function from the export-section needs
to be used the module name has to be given, too.
 
