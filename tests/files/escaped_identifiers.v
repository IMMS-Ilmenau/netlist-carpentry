module \weirdName-- (
    input \0input[] ,
    output \:out:put
);
    wire \someWire?? ;

    (* keep *) \subModule[1] \In$tance,.-+# (
        .A(\0input[] ),
        .B(\someWire?? )
    );

    assign \:out:put = \someWire?? ;
endmodule

module \subModule[1] (
    input A,
    output Y
);
    assign Y = ~A;
endmodule
